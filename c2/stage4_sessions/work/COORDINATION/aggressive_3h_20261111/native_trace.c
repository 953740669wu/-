#define _GNU_SOURCE
#include <execinfo.h>
#include <pthread.h>
#include <signal.h>
#include <unistd.h>

/* Diagnostic-only, bounded job: capture the actual training thread at 25 s. */
static pthread_t main_thread, timer_thread;
static void dump(int signal_number) {
    (void)signal_number;
    void *frames[96];
    const char label[] = "NATIVE_SDPA_TRACE_BEGIN\n";
    write(2, label, sizeof(label) - 1);
    backtrace_symbols_fd(frames, backtrace(frames, 96), 2);
}
static void *timer(void *unused) {
    (void)unused;
    sleep(25);
    pthread_kill(main_thread, SIGUSR1);
    return 0;
}
int trace_start(void) {
    struct sigaction action = {0};
    action.sa_handler = dump;
    action.sa_flags = SA_RESTART;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGUSR1, &action, 0)) return -1;
    main_thread = pthread_self();
    return pthread_create(&timer_thread, 0, timer, 0);
}
void trace_stop(void) {
    pthread_cancel(timer_thread);
    pthread_join(timer_thread, 0);
}
