#!/usr/bin/env python3
"""Verify this board's UBI, archive payload, FIT and physical partition policy."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct
import sys
import tarfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight_fit import parse_dtb, string, integer

cli=argparse.ArgumentParser()
cli.add_argument('factory', type=Path)
cli.add_argument('sysupgrade', type=Path)
cli.add_argument('output', type=Path)
cli.add_argument('--single', action='store_true')
args=cli.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
blob=args.factory.read_bytes()
assert len(blob)%131072==0
volumes={};contents={}
for offset in range(0,len(blob),131072):
    peb=blob[offset:offset+131072]
    assert peb[:4]==b'UBI#'
    assert struct.unpack_from('>I',peb,60)[0]==(zlib.crc32(peb[:60])^0xffffffff)
    vid,data_offset=struct.unpack_from('>II',peb,16)
    assert (vid,data_offset)==(2048,4096)
    header=peb[vid:vid+64]
    assert header[:4]==b'UBI!'
    assert struct.unpack_from('>I',header,60)[0]==(zlib.crc32(header[:60])^0xffffffff)
    volume,logical=struct.unpack_from('>II',header,8)
    if volume==0x7fffefff:
        for index in range(128):
            record=peb[data_offset+index*172:data_offset+(index+1)*172]
            assert struct.unpack_from('>I',record,168)[0]==(zlib.crc32(record[:168])^0xffffffff)
            reserved=struct.unpack_from('>I',record)[0]
            if not reserved:continue
            length=struct.unpack_from('>H',record,14)[0]
            item={'name':record[16:16+length].decode(),'reserved_pebs':reserved,
                  'type':record[12],'flags':record[144]}
            if index in volumes:assert volumes[index]==item
            volumes[index]=item
    else:
        contents.setdefault(volume,{})[logical]=peb[data_offset:]
assert len(volumes)==3
assert [volumes[i]['name'] for i in range(3)]==['kernel','rootfs','rootfs_data']
assert volumes[2]['flags']&1
with tarfile.open(args.sysupgrade,'r:') as archive:
    directory='sysupgrade-lingyan_lyw-30m' + ('-single' if args.single else '')
    assert set(archive.getnames())=={directory,directory+'/CONTROL',directory+'/kernel',directory+'/root'}
    kernel=archive.extractfile(directory+'/kernel').read()
    root=archive.extractfile(directory+'/root').read()
assert root[:4]==b'hsqs'
root_used=struct.unpack_from('<Q',root,40)[0]
assert root_used<=len(root) and not any(root[root_used:])
for number,payload in [(0,kernel),(1,root[:root_used])]:
    reconstructed=b''.join(contents[number][i] for i in range(len(contents[number])))
    assert reconstructed[:len(payload)]==payload
fit=parse_dtb(kernel)
assert string(fit['/configurations']['default'])=='config@mp03.3'
config=fit['/configurations/config@mp03.3']
image='/images/'+string(config['kernel'])
fdt='/images/'+string(config['fdt'])
assert string(fit[image]['arch'])=='arm64'
assert integer(fit[image]['load'])==integer(fit[image]['entry'])==0x41000000
payload=lzma.decompress(fit[image]['data'],format=lzma.FORMAT_ALONE)
assert payload[56:60]==b'ARM\x64'
assert len(payload)<0x1000000, 'Expected the NAND kernel without the large embedded RAM root'
for path,properties in fit.items():
    if path.startswith((image+'/hash',fdt+'/hash')):
        data=fit[path.rsplit('/',1)[0]]['data'];algo=string(properties['algo'])
        digest=struct.pack('>I',zlib.crc32(data)) if algo=='crc32' else hashlib.new(algo,data).digest()
        assert digest==properties['value']
tree=parse_dtb(fit[fdt]['data'])
parts={}
for path,properties in tree.items():
    if '/partitions/partition@' in path and '/' not in path.split('/partition@',1)[1]:
        parts[string(properties['label'])]=(struct.unpack('>II',properties['reg']),'read-only' in properties)
if args.single:
    assert len(parts)==16
    assert parts['rootfs']==((0x900000,0x7700000),False)
    assert {name for name,(_,ro) in parts.items() if not ro}=={'rootfs'}
    end=0
    for (offset,length),ro in sorted(parts.values()):
        assert offset==end
        end=offset+length
    assert end==0x8000000
    assert not {'stock_rootfs','rootfs_1','plugins'} & parts.keys()
else:
    assert len(parts)==18
    assert parts['stock_rootfs']==((0x900000,0x2840000),True)
    assert parts['rootfs']==((0x3140000,0x2840000),False)
    assert {name for name,(_,ro) in parts.items() if not ro}=={'0:BOOTCONFIG','0:BOOTCONFIG1','rootfs'}
assert b'root=/dev/ubiblock0_1' in tree['/chosen']['bootargs-append']
assert b'ubi.mtd=' not in tree['/chosen']['bootargs-append']
assert tree['/reserved-memory/tz@4ac00000']['reg']==struct.pack('>IIII',0,0x4ac00000,0,0x400000)
assert tree['/reserved-memory/nss@40000000']['reg']==struct.pack('>IIII',0,0x40000000,0,0x1000000)
need=sum(x['reserved_pebs'] for x in volumes.values())+41
target_pebs=952 if args.single else 322
assert need<=target_pebs
(args.output/'kernel.itb').write_bytes(kernel)
(args.output/'root-sysupgrade.squashfs').write_bytes(root)
(args.output/'root-factory.squashfs').write_bytes(root[:root_used])
report={'factory_bytes':len(blob),'factory_sha256':hashlib.sha256(blob).hexdigest(),
        'sysupgrade_sha256':hashlib.sha256(args.sysupgrade.read_bytes()).hexdigest(),
        'factory_pebs':len(blob)//131072,'target_pebs':target_pebs,'LEB':126976,
        'storage_layout':'single-ubi-v1' if args.single else 'legacy-slot1',
        'volumes':volumes,'conservative_capacity_pebs':need,
        'kernel_bytes':len(kernel),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),
        'root_factory_bytes':root_used,'root_sysupgrade_bytes':len(root),
        'root_factory_sha256':hashlib.sha256(root[:root_used]).hexdigest(),
        'root_sysupgrade_sha256':hashlib.sha256(root).hexdigest(),
        'partitions':parts,'kernel_fit_verified':True}
(args.output/'layout.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:value for key,value in report.items() if key!='partitions'},indent=2))
