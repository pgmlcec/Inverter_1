from setuptools import setup, find_packages

MAIN_MODULE = 'agent'

# Find the agent package that contains the main module
packages = find_packages('.')
agent_package = 'Mod_Comm'

# Find the version number from the main module
agent_module = agent_package + '.' + MAIN_MODULE
_temp = __import__(agent_module, globals(), locals(), ['__version__'], 0)
__version__ = _temp.__version__

# Setup
setup(
    name=agent_package + 'agent',
    version=__version__,
    author="Taha",
    author_email="taha112saeed@gmail.com",
    description="Modbus communication",
    install_requires=[
        'volttron',
        'pymodbus==3.6.4'  # Specify the pymodbus version you have installed or simply use 'pymodbus' for the latest version
    ],
    packages=packages,
    entry_points={
        'setuptools.installation': [
            'eggsecutable = ' + agent_module + ':main',
        ]
    }
)
