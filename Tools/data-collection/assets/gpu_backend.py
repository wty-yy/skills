"""Access NVML and the CUDA driver without a CUDA toolkit or Python packages."""

import ctypes as C
import os
from dataclasses import dataclass

MIB = 1024**2
GIB = 1024**3


class DriverError(RuntimeError):
    """Report a failed driver operation."""


class Library:
    """Bind the small subset of native functions used by the service."""

    def __init__(self, path):
        """Load an NVIDIA library supplied by the host driver."""
        self.lib = C.CDLL(path)

    def bind(self, name, *args):
        """Bind a checked integer-returning native function."""
        native = getattr(self.lib, name)
        native.argtypes = args
        native.restype = C.c_int

        def call(*values):
            """Translate native failure codes into Python exceptions."""
            result = native(*values)
            if result:
                raise DriverError(f"{name}: error {result}")

        return call


class ProcessInfo(C.Structure):
    """Match nvmlProcessInfo_t used by the v2 process query functions."""

    _fields_ = [("pid", C.c_uint), ("usedGpuMemory", C.c_ulonglong),
                ("gpuInstanceId", C.c_uint), ("computeInstanceId", C.c_uint)]


class MemoryInfo(C.Structure):
    """Match the NVML v1 memory information structure."""

    _fields_ = [("total", C.c_ulonglong), ("free", C.c_ulonglong),
                ("used", C.c_ulonglong)]


@dataclass(frozen=True)
class Process:
    """Keep process identity separate from its changing memory usage."""

    pid: int
    uid: int
    started: str
    memory: int
    compute: bool


class Monitor(Library):
    """Observe one physical GPU and resolve host process owners."""

    def __init__(self, uuid):
        """Resolve a stable GPU UUID and reject unsupported MIG devices."""
        super().__init__("libnvidia-ml.so.1")
        self.bind("nvmlInit_v2")()
        self.handle = C.c_void_p()
        self.bind("nvmlDeviceGetHandleByUUID", C.c_char_p, C.POINTER(C.c_void_p))(
            uuid.encode(), C.byref(self.handle))
        try:
            current, pending = C.c_uint(), C.c_uint()
            self.bind("nvmlDeviceGetMigMode", C.c_void_p, C.POINTER(C.c_uint),
                      C.POINTER(C.c_uint))(self.handle, C.byref(current), C.byref(pending))
            if current.value:
                raise RuntimeError("MIG enabled: use a physical GPU without MIG")
        except DriverError as error:
            if not str(error).endswith("error 3"):  # NVML_ERROR_NOT_SUPPORTED
                raise
        self.memory_query = self.bind("nvmlDeviceGetMemoryInfo", C.c_void_p,
                                      C.POINTER(MemoryInfo))

    def memory(self):
        """Read whole-device memory accounting."""
        info = MemoryInfo()
        self.memory_query(self.handle, C.byref(info))
        return info

    def process_list(self, kind):
        """Retry process enumeration when its buffer changes concurrently."""
        native = getattr(self.lib, f"nvmlDeviceGet{kind}RunningProcesses_v2")
        native.argtypes = [C.c_void_p, C.POINTER(C.c_uint), C.POINTER(ProcessInfo)]
        native.restype = C.c_int
        capacity = 64
        for _ in range(5):
            count = C.c_uint(capacity)
            buffer = (ProcessInfo * capacity)()
            result = native(self.handle, C.byref(count), buffer)
            if result == 0:
                return list(buffer[:count.value])
            if result != 7:  # NVML_ERROR_INSUFFICIENT_SIZE
                raise DriverError(f"NVML {kind} process query: error {result}")
            capacity = max(capacity * 2, count.value + 16)
        raise RuntimeError("GPU process list did not stabilize")

    def processes(self):
        """Merge compute and graphics PIDs, excluding this service itself."""
        entries = {}
        for kind in ("Graphics", "Compute"):
            for item in self.process_list(kind):
                if item.pid == os.getpid():
                    continue
                try:
                    path = f"/proc/{item.pid}"
                    uid = os.stat(path).st_uid
                    with open(f"{path}/comm", encoding="utf-8") as stream:
                        if stream.read().strip().startswith("nvidia-cuda-mps"):
                            raise RuntimeError("CUDA MPS is unsupported: client UID is not visible")
                    with open(f"{path}/stat", encoding="utf-8") as stream:
                        started = stream.read().rsplit(")", 1)[1].split()[19]
                except FileNotFoundError:
                    continue
                except PermissionError as error:
                    raise RuntimeError("Cannot read host /proc; check --pid=host/hidepid") from error
                if item.usedGpuMemory == 2**64 - 1:
                    raise RuntimeError("NVML cannot report per-process GPU memory")
                entries[item.pid] = Process(item.pid, uid, started, item.usedGpuMemory,
                                            kind == "Compute")
        return list(entries.values())

    def close(self):
        """Release the NVML client reference."""
        self.bind("nvmlShutdown")()


PTX = b"""
.version 6.0
.target sm_52
.address_size 64
.visible .entry pulse(.param .u64 cycles) {
    .reg .pred done;
    .reg .u64 start, now, elapsed, limit;
    ld.param.u64 limit, [cycles];
    mov.u64 start, %clock64;
again:
    mov.u64 now, %clock64;
    sub.u64 elapsed, now, start;
    setp.ge.u64 done, elapsed, limit;
    @!done bra again;
    ret;
}
"""


class Cuda(Library):
    """Own and release only the service's CUDA allocations and context."""

    def __init__(self, uuid):
        """Find the UUID among CUDA-visible devices and prepare a short kernel."""
        super().__init__("libcuda.so.1")
        self.bind("cuInit", C.c_uint)(0)
        count = C.c_int()
        self.bind("cuDeviceGetCount", C.POINTER(C.c_int))(C.byref(count))
        device = None
        get_uuid = self.bind("cuDeviceGetUuid", C.c_void_p, C.c_int)
        import uuid as uuid_module
        for index in range(count.value):
            value = C.create_string_buffer(16)
            get_uuid(value, index)
            if f"GPU-{uuid_module.UUID(bytes=value.raw)}" == uuid:
                device = index
                break
        if device is None:
            raise RuntimeError(f"GPU {uuid} is not CUDA-visible")
        self.context = C.c_void_p()
        self.bind("cuCtxCreate_v2", C.POINTER(C.c_void_p), C.c_uint, C.c_int)(
            C.byref(self.context), 0, device)
        self.blocks = C.c_int()
        self.bind("cuDeviceGetAttribute", C.POINTER(C.c_int), C.c_int, C.c_int)(
            C.byref(self.blocks), 16, device)  # MULTIPROCESSOR_COUNT
        self.module, self.kernel = C.c_void_p(), C.c_void_p()
        self.bind("cuModuleLoadData", C.POINTER(C.c_void_p), C.c_void_p)(
            C.byref(self.module), PTX)
        self.bind("cuModuleGetFunction", C.POINTER(C.c_void_p), C.c_void_p, C.c_char_p)(
            C.byref(self.kernel), self.module, b"pulse")
        self.alloc = self.bind("cuMemAlloc_v2", C.POINTER(C.c_uint64), C.c_size_t)
        self.free = self.bind("cuMemFree_v2", C.c_uint64)
        self.info = self.bind("cuMemGetInfo_v2", C.POINTER(C.c_size_t), C.POINTER(C.c_size_t))
        self.sync = self.bind("cuCtxSynchronize")
        self.launch = self.bind("cuLaunchKernel", C.c_void_p, *([C.c_uint] * 7),
                                C.c_void_p, C.POINTER(C.c_void_p), C.c_void_p)
        self.chunks = []
        self.cycles = 1_000_000

    @property
    def held(self):
        """Return bytes held by explicit reservation allocations."""
        return sum(size for _, size in self.chunks)

    def available(self):
        """Query free memory immediately before modifying reservations."""
        free, total = C.c_size_t(), C.c_size_t()
        self.info(C.byref(free), C.byref(total))
        return free.value

    def release(self):
        """Synchronously return every reservation chunk to the driver."""
        while self.chunks:
            self.free(self.chunks[-1][0])
            self.chunks.pop()

    def allocate(self, size):
        """Record one allocation so it can be released independently."""
        pointer = C.c_uint64()
        self.alloc(C.byref(pointer), size)
        self.chunks.append((pointer.value, size))

    def reconcile(self, reserve, chunk=64 * MIB):
        """Claim surplus memory without yielding reservations to foreign allocations."""
        for _ in range(16):
            free = self.available()
            if free >= reserve + chunk:
                try:
                    self.allocate(chunk)
                except DriverError as error:
                    if str(error).endswith("error 2"):  # CUDA_ERROR_OUT_OF_MEMORY
                        break
                    raise
            else:
                break

    def pulse(self):
        """Run a short kernel and adapt its duration towards three milliseconds."""
        import time
        cycles = C.c_uint64(self.cycles)
        parameters = (C.c_void_p * 1)(C.addressof(cycles))
        start = time.monotonic()
        self.launch(self.kernel, self.blocks.value, 1, 1, 128, 1, 1, 0,
                    None, parameters, None)
        self.sync()
        elapsed = time.monotonic() - start
        self.cycles = int(max(10_000, min(10_000_000,
                                        self.cycles * min(2, 0.003 / max(elapsed, 0.00001)))))
        return elapsed

    def close(self):
        """Destroy the context, releasing all remaining allocations on exit."""
        self.bind("cuCtxDestroy_v2", C.c_void_p)(self.context)
