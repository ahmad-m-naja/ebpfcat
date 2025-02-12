"""A simple example of an EtherCat control

this is only an illustrative example to be read. It will not work unless
you happen to have an EtherCat setup where a Beckhoff EL4101 terminal is
the second terminal in the line.
"""
import asyncio
from ebpfcat.ebpfcat import FastEtherCat, SyncGroup
from ebpfcat.devices import AnalogOutput, AnalogInput
from ebpfcat.terminals import EL3612, EL4102


async def main():
    master = FastEtherCat("eth0")
    await master.connect()
    print("Number of terminals:", await master.count())
    
    _in = EL3612(master)
    await _in.initialize(-1, 10) 
    ai = AnalogInput(_in.ch1_value)
    
    _out = EL4102(master)
    await _out.initialize(-2, 20) 
    ao = AnalogOutput(_out.ch1_value)
    
    sg = SyncGroup(master, [ao, ai])
    task = sg.start()  # start operating the terminals
    
    print(ao.value, ai.value)
    await asyncio.sleep(1)
    
    ao.value = 10
    #ai.update()
    
    for i in range(10):
        ao.value = i
        await asyncio.sleep(0.1)
        print(ao.value, ai.value)
    
    task.cancel()  # stop the sync group

asyncio.run(main())