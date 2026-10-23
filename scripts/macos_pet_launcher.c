/* Generated runtime paths are supplied by install_macos_pet.py. */
#include <Python.h>
#include <CoreFoundation/CoreFoundation.h>
#include <string.h>

static void startup_error(int checking) {
    if (!checking) {
        CFUserNotificationDisplayAlert(
            0, kCFUserNotificationStopAlertLevel, NULL, NULL, NULL,
            CFSTR("TOMC could not start"),
            CFSTR("Keep the Python environment and TOMC source used to install this app. "
                  "Run its installer again after moving or updating them. "
                  "The app's Contents/Resources/README.txt lists its dependencies."),
            CFSTR("OK"), NULL, NULL, NULL);
    }
}

int main(int argc, char **argv) {
    int checking = argc == 2 && strcmp(argv[1], "--tomc-launcher-check") == 0;
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.parse_argv = 0;
    config.site_import = 0;
    config.write_bytecode = 0;
    PyStatus status = PyConfig_SetBytesString(&config, &config.home, @PYTHON_HOME@);
    if (!PyStatus_Exception(status)) {
        status = PyConfig_SetBytesString(&config, &config.program_name, @PYTHON_EXECUTABLE@);
    }
    if (!PyStatus_Exception(status)) {
        status = PyConfig_SetBytesArgv(&config, argc, argv);
    }
    if (!PyStatus_Exception(status)) {
        status = Py_InitializeFromConfig(&config);
    }
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        startup_error(checking);
        Py_ExitStatusException(status);
    }
    int result = PyRun_SimpleString(@BOOTSTRAP@);
    if (result != 0) {
        startup_error(checking);
    }
    if (Py_FinalizeEx() < 0) {
        return 120;
    }
    return result == 0 ? 0 : 1;
}
