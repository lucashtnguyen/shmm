import sys
import os


TASKS = r"""\
{{
    "version": "0.1.0",
    "isShellCommand": false,
    "args": [],
    "showOutput": "always",
    "echoCommand": false,
    "suppressTaskName": false,
    "tasks": [
        {{
            "taskName": "test",
            "command": "{pyexec:s}",
            "args": [
                "check_{modulename:s}.py",
                "--cov",
                "--pep8"
            ]
        }},
        {{
            "taskName": "notebooks",
            "options": {{
                "cwd": "${{workspaceRoot}}/docs/tutorial"
            }},
            "command": "{pyexec:s}",
            "args": ["make.py"]
        }},
        {{
            "taskName": "docs",
            "options": {{
                "cwd": "${{workspaceRoot}}/docs"
            }},
            "command": "make.bat",
            "args": ["html"]
        }}
    ]
}}
"""

SETTINGS = r"""\
// Place your settings in this file to overwrite default and user settings.
{
    "python.pythonPath": {pyexec:s},
    "python.linting.pep8Enabled": true,
    "python.linting.pylintEnabled": false,
    "python.unitTest.pyTestEnabled": true,
    "python.unitTest.pyTestArgs": [
        "--cov",
        "--pep8",
        "--verbose"
    ]
}
"""

if __name__ == '__main__':
    dirname = ".vscode"
    filename = "tasks.json"

    filepath = os.path.join(dirname, filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    if len(sys.argv) < 2:
        name = os.path.split(os.getcwd())[-1]
    else:
        name = sys.argv[1]

    python = '/'.join(sys.executable.split(os.path.sep))
    config = TASKS.format(pyexec=python, modulename=name)

    with open(filepath, 'w') as configfile:
        configfile.write(config)
