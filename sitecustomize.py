import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOCAL_PACKAGES = os.path.join(PROJECT_ROOT, ".python-packages")

if os.path.isdir(LOCAL_PACKAGES) and LOCAL_PACKAGES not in sys.path:
    sys.path.insert(0, LOCAL_PACKAGES)
