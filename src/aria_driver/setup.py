from glob import glob

from setuptools import find_packages, setup

package_name = 'aria_driver'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='phdminh01',
    maintainer_email='phdminh01@gmail.com',
    description='ROS 2 node for Project Aria Gen2 glasses',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'aria_node = aria_driver.aria_node:main',
            'aria_device = aria_driver.device_cli:main',
            'tts_prompt = aria_driver.tts_prompt:main',
            'to_mp4 = aria_driver.to_mp4:main',
        ],
    },
)
