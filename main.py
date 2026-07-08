"""
main.py
-------
Deployment entry point (required by pyside6-deploy/Nuitka).

The installed console script (``wizard_4155_4156``) remains the entry
point for development; this file only exists so the deployment tool has
a script with a ``__main__`` guard to compile.
"""

from wizard_4155_4156 import main

if __name__ == "__main__":
    main()
