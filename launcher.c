#include <limits.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

static void show_dialog(const char *message) {
    char command[4096];
    snprintf(
        command,
        sizeof(command),
        "/usr/bin/osascript -e 'display dialog \"%s\" buttons {\"OK\"} "
        "default button \"OK\" with title \"OpenAI Chat\"'",
        message
    );
    system(command);
}

static void dirname_in_place(char *path) {
    char *slash = strrchr(path, '/');
    if (slash != NULL) {
        *slash = '\0';
    }
}

static int worker_is_running(const char *pid_path) {
    FILE *pid_file = fopen(pid_path, "r");
    if (pid_file == NULL) {
        return 0;
    }

    long pid = 0;
    int scanned = fscanf(pid_file, "%ld", &pid);
    fclose(pid_file);

    if (scanned != 1 || pid <= 0) {
        unlink(pid_path);
        return 0;
    }

    if (kill((pid_t)pid, 0) == 0 || errno == EPERM) {
        return 1;
    }

    unlink(pid_path);
    return 0;
}

static void start_background_script(
    const char *python_path,
    const char *app_dir,
    const char *script_name,
    const char *pid_name,
    const char *log_name
) {
    char script_path[PATH_MAX];
    char log_path[PATH_MAX];
    char pid_path[PATH_MAX];

    snprintf(script_path, sizeof(script_path), "%s/%s", app_dir, script_name);
    if (access(script_path, R_OK) != 0) {
        return;
    }

    snprintf(pid_path, sizeof(pid_path), "%s/%s", app_dir, pid_name);
    if (worker_is_running(pid_path)) {
        return;
    }

    pid_t child = fork();
    if (child != 0) {
        return;
    }

    setsid();
    chdir(app_dir);

    snprintf(log_path, sizeof(log_path), "%s/%s", app_dir, log_name);
    int log_fd = open(log_path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (log_fd >= 0) {
        dup2(log_fd, STDOUT_FILENO);
        dup2(log_fd, STDERR_FILENO);
        close(log_fd);
    }

    int dev_null = open("/dev/null", O_RDONLY);
    if (dev_null >= 0) {
        dup2(dev_null, STDIN_FILENO);
        close(dev_null);
    }

    FILE *pid_file = fopen(pid_path, "w");
    if (pid_file != NULL) {
        fprintf(pid_file, "%ld\n", (long)getpid());
        fclose(pid_file);
    }

    char *script_args[] = {
        (char *)python_path,
        script_path,
        NULL,
    };

    execv(python_path, script_args);
    _exit(127);
}

int main(int argc, char *argv[]) {
    char executable_path[PATH_MAX];
    char app_dir[PATH_MAX];
    char python_path[PATH_MAX];
    char main_path[PATH_MAX];

    if (realpath(argv[0], executable_path) == NULL) {
        show_dialog("Could not locate the app bundle.");
        return 1;
    }

    strncpy(app_dir, executable_path, sizeof(app_dir));
    app_dir[sizeof(app_dir) - 1] = '\0';
    dirname_in_place(app_dir); /* Contents/MacOS */
    dirname_in_place(app_dir); /* Contents */
    dirname_in_place(app_dir); /* app root */

    snprintf(python_path, sizeof(python_path), "%s/.venv/bin/python", app_dir);
    if (access(python_path, X_OK) != 0) {
        strncpy(python_path, "/usr/bin/python3", sizeof(python_path));
        python_path[sizeof(python_path) - 1] = '\0';
    }

    char *check_args[] = {
        python_path,
        "-c",
        "import PySide6, openai",
        NULL,
    };

    pid_t child = fork();
    if (child == 0) {
        execv(python_path, check_args);
        _exit(127);
    }

    int status = 0;
    if (child < 0 || waitpid(child, &status, 0) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        show_dialog("OpenAI Chat dependencies are not installed yet. Open Terminal in this project folder and run: python3 -m venv .venv; source .venv/bin/activate; pip install -r requirements.txt");
        return 1;
    }

    start_background_script(python_path, app_dir, "app.py", ".app.py.pid", "app.log");
    start_background_script(python_path, app_dir, "saveApp.py", ".saveApp.pid", "saveApp.log");

    snprintf(main_path, sizeof(main_path), "%s/main.py", app_dir);
    char *run_args[] = {
        python_path,
        main_path,
        NULL,
    };

    execv(python_path, run_args);
    show_dialog("Could not start the Python app.");
    return 1;
}
