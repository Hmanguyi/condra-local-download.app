#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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
        "import PySide6, openai, keyring",
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
