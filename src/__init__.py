import importlib
import sys

# Re-export program.src under the 'src' namespace for backward compatibility
module = importlib.import_module('program.src')
# Replace this module with the actual program.src package
sys.modules[__name__] = module
# Register submodules under the 'src.' prefix as well
for name, mod in list(sys.modules.items()):
    if name.startswith('program.src.'):
        sys.modules.setdefault('src.' + name[len('program.src.'):], mod)
