from argparse import ArgumentParser
import asyncio
from functools import wraps
from hashlib import sha1
from struct import unpack
import sys

from .ethercat import EtherCat, Terminal, ECCmd

def entrypoint(func):
    @wraps(func)
    def wrapper():
        asyncio.run(func())
    return wrapper


@entrypoint
async def scanbus():
    ec = EtherCat(sys.argv[1])
    await ec.connect()
    no = await ec.count()
    for i in range(no):
        r, = await ec.roundtrip(ECCmd.APRD, -i, 0x10, "H", 44)
        print(i, r)

@entrypoint
async def info():
    parser = ArgumentParser(
        prog = "ec-info",
        description = "Retrieve information from an EtherCat bus")

    parser.add_argument("interface")
    parser.add_argument("-t", "--terminal", type=int)
    parser.add_argument("-i", "--ids", action="store_true")
    parser.add_argument("-n", "--names", action="store_true")
    parser.add_argument("-s", "--sdo", action="store_true")
    parser.add_argument("-v", "--values", action="store_true")
    parser.add_argument("-p", "--pdo", action="store_true")
    args = parser.parse_args()

    ec = EtherCat(args.interface)
    await ec.connect()

    if args.terminal is None:
        terminals = range(await ec.count())
        terms = [Terminal() for t in terminals]
        for t in terms:
            t.ec = ec
        await asyncio.gather(*(t.initialize(-i, i + 7)
                               for i, t in zip(terminals, terms)))
    else:
        free = await ec.find_free_address()
        term = Terminal()
        term.ec = ec
        await term.initialize(-args.terminal, free)
        terms = [term]

    for i, t in enumerate(terms):
        print(f"terminal no {i}")
        if args.ids:
            print(f"{t.vendorId:X}:{t.productCode:X} "
                  f"revision {t.revisionNo:X} serial {t.serialNo}")
        if args.names:
            infos = t.eeprom[10]
            i = 1
            while i < len(infos):
                print(infos[i+1 : i+infos[i]+1].decode("ascii"))
                i += infos[i] + 1

        if args.sdo:
            await t.to_operational()
            ret = await t.read_ODlist()
            for k, v in ret.items():
                print(f"{k:X}:")
                for kk, vv in v.entries.items():
                     print(f"    {kk:X}: {vv}")
                     if args.values:
                         r = await vv.read()
                         if isinstance(r, int):
                             print(f"        {r:10} {r:8X}")
                         else:
                             print(f"        {r}")
        if args.pdo:
            await t.to_operational()
            await t.parse_pdos()
            for (idx, subidx), (sm, pos, fmt) in t.pdos.items():
                print(f"{idx:4X}:{subidx:02X} {sm} {pos} {fmt}")


def encode(name):
    r = int.from_bytes(sha1(name.encode("ascii")).digest(), "little")
    return r % 0xffffffff + 1

@entrypoint
async def eeprom():
    parser = ArgumentParser(
        prog = "ec-eeprom",
        description = "Read and write the eeprom")

    parser.add_argument("interface")
    parser.add_argument("-t", "--terminal", type=int)
    parser.add_argument("-r", "--read", action="store_true")
    parser.add_argument("-w", "--write", type=int)
    parser.add_argument("-n", "--name", type=str)
    parser.add_argument("-c", "--check", type=str)
    args = parser.parse_args()

    ec = EtherCat(args.interface)
    await ec.connect()

    if args.terminal is None:
        return
        terminals = range(await ec.count())
    else:
        # former terminal: don't listen!
        # this does not work with all terminals, dunno why
        await ec.roundtrip(ECCmd.FPRW, 7, 0x10, "H", 0)
        terminals = [args.terminal]

    t = Terminal()
    t.ec = ec
    await t.initialize(-args.terminal, 7)

    if args.read or args.check is not None:
        r, = unpack("<4xI", await t.eeprom_read_one(0xc))
        if args.check is not None:
            c = encode(args.check)
            print(f"{r:8X} {c:8X} {r == c}")
        else:
            print(f"{r:8X} {r}")

    w = None
    if args.write is not None:
        w = args.write
    elif args.name is not None:
        w = encode(args.name)
        print(f"{w:8X} {w}")
    if w is not None:
        await t.eeprom_write_one(0xe, w & 0xffff)
        await t.eeprom_write_one(0xf, w >> 16)
