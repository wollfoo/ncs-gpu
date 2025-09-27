// Package cgo provides CGO bindings to Rust core
package cgo

/*
#cgo LDFLAGS: -L../../../../target/release -lopus_gpu_core
#cgo CFLAGS: -I../../../../core/include

#include <stdint.h>
#include <stdlib.h>

// Task structure matching Rust PluginTask
typedef struct {
    char* id;
    char* type_;
    uint8_t* payload;
    size_t payload_len;
    uint8_t priority;
} RustTask;

// Function declarations
extern void* opus_init_runtime(const char* config_path);
extern void opus_shutdown_runtime(void* runtime);
extern int opus_submit_task(void* runtime, RustTask task);
extern void* opus_get_task_result(void* runtime, const char* task_id);
extern void opus_free_result(void* result);
extern int opus_get_gpu_count();
extern double opus_get_gpu_utilization(int device_id);
*/
import "C"
import (
	"fmt"
	"unsafe"
)

// RuntimeHandle wraps the Rust runtime pointer
type RuntimeHandle struct {
	ptr unsafe.Pointer
}

// Task represents a GPU task
type Task struct {
	ID       string
	Type     string
	Payload  []byte
	Priority uint8
}

// NewRuntime initializes the Rust runtime
func NewRuntime(configPath string) (*RuntimeHandle, error) {
	cPath := C.CString(configPath)
	defer C.free(unsafe.Pointer(cPath))
	
	ptr := C.opus_init_runtime(cPath)
	if ptr == nil {
		return nil, fmt.Errorf("failed to initialize Rust runtime")
	}
	
	return &RuntimeHandle{ptr: ptr}, nil
}

// Shutdown cleans up the runtime
func (r *RuntimeHandle) Shutdown() {
	if r.ptr != nil {
		C.opus_shutdown_runtime(r.ptr)
		r.ptr = nil
	}
}

// SubmitTask sends a task to the Rust runtime
func (r *RuntimeHandle) SubmitTask(task Task) error {
	if r.ptr == nil {
		return fmt.Errorf("runtime not initialized")
	}
	
	// Convert Go task to C task
	cTask := C.RustTask{
		id:    C.CString(task.ID),
		type_: C.CString(task.Type),
		priority: C.uint8_t(task.Priority),
	}
	defer C.free(unsafe.Pointer(cTask.id))
	defer C.free(unsafe.Pointer(cTask.type_))
	
	if len(task.Payload) > 0 {
		cTask.payload = (*C.uint8_t)(C.CBytes(task.Payload))
		cTask.payload_len = C.size_t(len(task.Payload))
		defer C.free(unsafe.Pointer(cTask.payload))
	}
	
	result := C.opus_submit_task(r.ptr, cTask)
	if result != 0 {
		return fmt.Errorf("failed to submit task")
	}
	
	return nil
}

// GetTaskResult retrieves the result of a completed task
func (r *RuntimeHandle) GetTaskResult(taskID string) ([]byte, error) {
	if r.ptr == nil {
		return nil, fmt.Errorf("runtime not initialized")
	}
	
	cID := C.CString(taskID)
	defer C.free(unsafe.Pointer(cID))
	
	resultPtr := C.opus_get_task_result(r.ptr, cID)
	if resultPtr == nil {
		return nil, fmt.Errorf("task result not found")
	}
	defer C.opus_free_result(resultPtr)
	
	// Convert result to Go slice
	// In real implementation, would need proper structure
	return []byte{}, nil
}

// GetGPUCount returns the number of available GPUs
func GetGPUCount() int {
	return int(C.opus_get_gpu_count())
}

// GetGPUUtilization returns the utilization of a specific GPU
func GetGPUUtilization(deviceID int) float64 {
	return float64(C.opus_get_gpu_utilization(C.int(deviceID)))
}
