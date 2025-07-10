#!/usr/bin/env python3
"""
Simple Device Discovery Script
Run this to see what raw data and sensors your device supports
"""

import asyncio
import time
from buttplug import Client, WebsocketConnector, ProtocolSpec
from buttplug.messages import v3

class DeviceExplorer:
    def __init__(self):
        self.client = None
        self.device = None
        
    async def connect(self):
        """Connect to Intiface Central"""
        try:
            print("🔌 Connecting to Intiface Central...")
            self.client = Client("Device Explorer", ProtocolSpec.v3)
            connector = WebsocketConnector("ws://localhost:12345")
            await self.client.connect(connector)
            print("✅ Connected!")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("Make sure Intiface Central is running on port 12345")
            return False
            
    async def list_devices(self):
        """List all available devices"""
        # First, explicitly request device list (like MuchFun does)
        try:
            print("📋 Requesting device list...")
            device_list = await self.client.send(v3.RequestDeviceList())
            
            # Small delay to let devices populate
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️  Error requesting device list: {e}")
        
        devices = self.client.devices
        print(f"\n📱 Found {len(devices)} device(s):")
        
        for device_id, device in devices.items():
            print(f"  [{device_id}] {device.name}")
            
        if len(devices) > 0:
            # Use first device
            self.device = list(devices.values())[0]
            print(f"\n🎯 Using device: {self.device.name}")
            return True
        else:
            print("❌ No devices found. Make sure your device is connected and detected in Intiface Central.")
            print("💡 Try these steps:")
            print("   1. Check that your device is ON and in pairing mode")
            print("   2. In Intiface Central, click 'Start Scanning'")
            print("   3. Wait for your device to appear in the device list")
            print("   4. Click 'Stop Scanning' once it appears")
            print("   5. Run this script again")
            return False
            
    async def explore_capabilities(self):
        """Explore device capabilities"""
        if not self.device:
            return
            
        print(f"\n🔍 Exploring {self.device.name} capabilities...")
        print("=" * 50)
        
        # Basic actuators
        print(f"🎛️  Actuators: {len(self.device.actuators)}")
        for i, actuator in enumerate(self.device.actuators):
            print(f"   [{i}] Type: {getattr(actuator, 'type', 'Generic')}")
            print(f"       Description: {getattr(actuator, 'description', 'N/A')}")
            print(f"       Step Count: {getattr(actuator, 'step_count', 'N/A')}")
            
        # Linear actuators
        print(f"↕️  Linear Actuators: {len(self.device.linear_actuators)}")
        for i, actuator in enumerate(self.device.linear_actuators):
            print(f"   [{i}] Description: {getattr(actuator, 'description', 'N/A')}")
            
        # Rotatory actuators  
        print(f"🔄 Rotatory Actuators: {len(self.device.rotatory_actuators)}")
        for i, actuator in enumerate(self.device.rotatory_actuators):
            print(f"   [{i}] Description: {getattr(actuator, 'description', 'N/A')}")
            
        # Sensors
        print(f"📊 Sensors: {len(self.device.sensors)}")
        for i, sensor in enumerate(self.device.sensors):
            print(f"   [{i}] Type: {getattr(sensor, 'type', 'Unknown')}")
            print(f"       Description: {getattr(sensor, 'description', 'N/A')}")
            print(f"       Subscribable: {hasattr(sensor, 'subscribe')}")
            if hasattr(sensor, 'ranges'):
                print(f"       Ranges: {sensor.ranges}")
                
    async def test_sensors(self):
        """Test reading sensor data"""
        if not self.device.sensors:
            print("\n📊 No sensors to test")
            return
            
        print(f"\n📊 Testing {len(self.device.sensors)} sensor(s)...")
        print("-" * 30)
        
        for i, sensor in enumerate(self.device.sensors):
            sensor_type = getattr(sensor, 'type', 'Unknown')
            print(f"\n🔬 Testing sensor {i}: {sensor_type}")
            
            # Try to read sensor data
            try:
                if hasattr(sensor, 'read'):
                    data = await sensor.read()
                    print(f"   ✅ Read successful: {data}")
                else:
                    # Try with SensorReadCmd
                    message = await self.client.send(v3.SensorReadCmd(
                        self.device.index,
                        i,
                        sensor_type
                    ))
                    
                    if hasattr(message, 'data'):
                        print(f"   ✅ Raw read successful: {message.data}")
                    else:
                        print(f"   ⚠️  Read response: {type(message).__name__}")
                        
            except Exception as e:
                print(f"   ❌ Read failed: {e}")
                
            # Try subscribing if possible
            if hasattr(sensor, 'subscribe'):
                try:
                    print(f"   🔔 Attempting to subscribe...")
                    await sensor.subscribe(lambda data, idx=i: self.on_sensor_data(idx, data))
                    print(f"   ✅ Subscription successful!")
                except Exception as e:
                    print(f"   ❌ Subscription failed: {e}")
                    
    def on_sensor_data(self, sensor_index, data):
        """Handle sensor data"""
        print(f"   📈 Sensor {sensor_index} data: {data}")
        
    async def test_raw_endpoints(self):
        """Test common raw endpoints"""
        print(f"\n🔌 Testing raw endpoints...")
        print("-" * 30)
        
        # Common endpoints to try
        endpoints_to_test = ["tx", "rx", "cmd", "data", "control", "sensor"]
        
        for endpoint in endpoints_to_test:
            print(f"\n📡 Testing endpoint: '{endpoint}'")
            
            # Try writing simple data
            try:
                message = await self.client.send(v3.RawWriteCmd(
                    self.device.index,
                    endpoint,
                    [0x00, 0x01, 0x02],  # Simple test data
                    write_with_response=False
                ))
                
                if hasattr(message, 'error_code'):
                    print(f"   ❌ Write failed: {message.error_message}")
                else:
                    print(f"   ✅ Write successful to '{endpoint}'")
                    
            except Exception as e:
                print(f"   ❌ Write error: {e}")
                
            # Try reading from endpoint
            try:
                message = await self.client.send(v3.RawReadCmd(
                    self.device.index,
                    endpoint,
                    expected_length=10,
                    wait_for_data=False
                ))
                
                if hasattr(message, 'data') and message.data:
                    print(f"   ✅ Read successful: {message.data}")
                elif hasattr(message, 'error_code'):
                    print(f"   ⚠️  Read failed: {message.error_message}")
                else:
                    print(f"   ⚠️  No data available")
                    
            except Exception as e:
                print(f"   ❌ Read error: {e}")
                
            # Try subscribing to endpoint
            try:
                message = await self.client.send(v3.RawSubscribeCmd(
                    self.device.index,
                    endpoint
                ))
                
                if hasattr(message, 'error_code'):
                    print(f"   ❌ Subscribe failed: {message.error_message}")
                else:
                    print(f"   ✅ Subscribe successful to '{endpoint}'")
                    
            except Exception as e:
                print(f"   ❌ Subscribe error: {e}")
                
    async def monitor_for_data(self, duration=10):
        """Monitor for incoming sensor/raw data"""
        print(f"\n👀 Monitoring for {duration} seconds...")
        print("   (Try interacting with your device)")
        print("-" * 30)
        
        start_time = time.time()
        data_received = False
        
        while time.time() - start_time < duration:
            print(".", end="", flush=True)
            await asyncio.sleep(1)
            
        print(f"\n{'✅ Data received during monitoring!' if data_received else '⚠️  No data received'}")
        
    async def device_info_dump(self):
        """Dump all available device information"""
        if not self.device:
            return
            
        print(f"\n📋 Complete device information dump...")
        print("=" * 50)
        
        # Device basic info
        print(f"Name: {self.device.name}")
        print(f"Index: {self.device.index}")
        print(f"Removed: {getattr(self.device, 'removed', 'N/A')}")
        
        # Try to access internal attributes
        for attr in dir(self.device):
            if not attr.startswith('_') and not callable(getattr(self.device, attr)):
                try:
                    value = getattr(self.device, attr)
                    print(f"{attr}: {value}")
                except:
                    pass
                    
        # Check if device has message info
        if hasattr(self.device, '_device_messages'):
            print(f"\nSupported messages:")
            for msg_type, msg_info in self.device._device_messages.items():
                print(f"  {msg_type}: {msg_info}")
                
    async def run_exploration(self):
        """Run complete device exploration"""
        print("🚀 Device Explorer Starting...")
        print("This will discover what your device can do!")
        
        # Connect
        if not await self.connect():
            return
            
        # Find devices
        if not await self.list_devices():
            return
            
        # Explore capabilities
        await self.explore_capabilities()
        
        # Test sensors
        await self.test_sensors()
        
        # Test raw endpoints
        await self.test_raw_endpoints()
        
        # Monitor for live data
        await self.monitor_for_data(10)
        
        # Full info dump
        await self.device_info_dump()
        
        print(f"\n✅ Exploration complete!")
        print(f"📝 Summary for {self.device.name}:")
        print(f"   • {len(self.device.actuators)} actuator(s)")
        print(f"   • {len(self.device.linear_actuators)} linear actuator(s)")
        print(f"   • {len(self.device.rotatory_actuators)} rotatory actuator(s)")
        print(f"   • {len(self.device.sensors)} sensor(s)")
        
        # Disconnect
        await self.client.disconnect()
        print("🔌 Disconnected")

async def main():
    """Main function"""
    explorer = DeviceExplorer()
    await explorer.run_exploration()

if __name__ == "__main__":
    print("Device Discovery Script")
    print("Make sure Intiface Central is running with your device connected!")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    input("\nPress Enter to exit...")