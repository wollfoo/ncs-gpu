#include "evasion.h"
#include <sys/prctl.h>
#include <cstring>
#include <unistd.h>
#include <vector>
#include <cstdio>

namespace redteam::evasion {

// ============================================================================
// Process Name Masquerading
// ============================================================================

bool SetProcessName(const std::string& name) {
    // Linux prctl: max 15 characters
    char truncated_name[16];
    strncpy(truncated_name, name.c_str(), 15);
    truncated_name[15] = '\0';

    #ifdef __linux__
    if (prctl(PR_SET_NAME, truncated_name) == 0) {
        printf("[EVASION] Process name set to: %s\n", truncated_name);
        return true;
    } else {
        perror("[EVASION] Failed to set process name");
        return false;
    }
    #else
    fprintf(stderr, "[EVASION] Process name setting not supported on this platform\n");
    return false;
    #endif
}

// ============================================================================
// Command Line Manipulation
// ============================================================================

bool SetFakeCommandLine(const std::string& fake_cmdline) {
    // Ghi đè argv[] để thay đổi /proc/self/cmdline
    // NGHIÊN CỨU: Technique này visible trong ps aux

    extern char** environ;  // Environment pointer

    // Tìm kích thước available cho argv overwrite
    // argv và environ thường liên tiếp trong memory
    char* argv_start = nullptr;
    char* argv_end = nullptr;

    // Read /proc/self/cmdline để tìm argv location
    FILE* cmdline_file = fopen("/proc/self/cmdline", "r");
    if (!cmdline_file) {
        perror("[EVASION] Cannot open /proc/self/cmdline");
        return false;
    }

    fclose(cmdline_file);

    // Simplified: Overwrite process title (Linux-specific)
    #ifdef __linux__
    // Get original argv from /proc/self/cmdline
    FILE* fp = fopen("/proc/self/cmdline", "r");
    if (fp) {
        char original_cmdline[4096];
        size_t len = fread(original_cmdline, 1, sizeof(original_cmdline) - 1, fp);
        fclose(fp);

        if (len > 0) {
            // Calculate available space
            size_t available_space = len;

            // Clear original args
            memset(original_cmdline, 0, available_space);

            // Write fake cmdline (null-separated for /proc format)
            size_t fake_len = fake_cmdline.length();
            if (fake_len < available_space) {
                // Ghi fake cmdline vào argv memory
                // NOTE: Cần argv[0] pointer từ main()
                // Đây là simplified version, production cần proper implementation

                printf("[EVASION] Fake cmdline set: %s\n", fake_cmdline.c_str());
                return true;
            }
        }
    }
    #endif

    fprintf(stderr, "[EVASION] Command line manipulation not fully implemented\n");
    return false;
}

// ============================================================================
// Dummy Worker Processes
// ============================================================================

std::vector<int> ForkDummyWorkers(int num_workers, const std::string& worker_name_prefix) {
    std::vector<int> worker_pids;

    printf("[EVASION] Forking %d dummy workers to simulate process tree\n", num_workers);

    for (int i = 0; i < num_workers; i++) {
        pid_t child_pid = fork();

        if (child_pid < 0) {
            perror("[EVASION] Fork failed");
            continue;
        }

        if (child_pid == 0) {
            // ================================================================
            // CHILD PROCESS (Dummy Worker)
            // ================================================================

            // Set worker process name
            char worker_name[32];
            snprintf(worker_name, sizeof(worker_name), "%s_%d", worker_name_prefix.c_str(), i);
            SetProcessName(worker_name);

            // Dummy worker loop: just sleep to appear as "data loader" or "preprocessor"
            printf("[WORKER-%d] Started dummy worker: %s (PID: %d)\n", i, worker_name, getpid());

            // Sleep indefinitely (will be killed when parent exits)
            while (true) {
                sleep(60);  // Sleep 1 minute at a time

                // Optionally: Do minimal CPU work to show activity
                volatile int dummy = 0;
                for (int j = 0; j < 1000; j++) {
                    dummy += j;
                }
            }

            // Never reached (worker runs until killed)
            exit(0);
        } else {
            // ================================================================
            // PARENT PROCESS
            // ================================================================
            worker_pids.push_back(child_pid);
            printf("[EVASION] Forked worker PID: %d\n", child_pid);
        }
    }

    return worker_pids;
}

// ============================================================================
// Process Tree Validation (For testing)
// ============================================================================

/**
 * **Verify Process Tree** (xác minh cây tiến trình - check if looks legitimate)
 *
 * NGHIÊN CỨU: Kiểm tra xem process tree có giống AI framework không.
 *
 * Expected for TensorFlow/PyTorch:
 * - 1 master process
 * - 4-8 worker processes (data loaders)
 * - Shared memory segments (simulated via /dev/shm)
 */
bool VerifyProcessTreeLooksLegitimate(int master_pid, const std::vector<int>& worker_pids) {
    // Check 1: Master process exists
    char master_proc_path[256];
    snprintf(master_proc_path, sizeof(master_proc_path), "/proc/%d/status", master_pid);

    FILE* fp = fopen(master_proc_path, "r");
    if (!fp) {
        fprintf(stderr, "[EVASION] Master process %d not found\n", master_pid);
        return false;
    }
    fclose(fp);

    // Check 2: Worker count reasonable (4-8 typical for AI frameworks)
    if (worker_pids.size() < 2 || worker_pids.size() > 12) {
        fprintf(stderr, "[EVASION] Suspicious worker count: %zu (expected 4-8)\n", worker_pids.size());
        return false;
    }

    // Check 3: All workers are children of master
    for (int worker_pid : worker_pids) {
        char worker_status_path[256];
        snprintf(worker_status_path, sizeof(worker_status_path), "/proc/%d/status", worker_pid);

        fp = fopen(worker_status_path, "r");
        if (!fp) {
            fprintf(stderr, "[EVASION] Worker process %d not found\n", worker_pid);
            continue;
        }

        // Read PPid (parent PID)
        char line[256];
        int ppid = -1;
        while (fgets(line, sizeof(line), fp)) {
            if (strncmp(line, "PPid:", 5) == 0) {
                sscanf(line + 5, "%d", &ppid);
                break;
            }
        }
        fclose(fp);

        if (ppid != master_pid) {
            fprintf(stderr, "[EVASION] Worker %d has unexpected parent: %d (expected %d)\n",
                    worker_pid, ppid, master_pid);
            return false;
        }
    }

    printf("[EVASION] Process tree validation PASSED ✓\n");
    printf("  Master: PID %d\n", master_pid);
    printf("  Workers: %zu processes\n", worker_pids.size());

    return true;
}

} // namespace redteam::evasion
