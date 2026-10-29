"""Bounded ZIP/ZIP64 directory walk before stdlib may allocate any ZipInfo.
Single disk, no concatenation offset correction/trailing data; standard44-byte ZIP64 EOCD supported.
APK signing blocks before the central directory are retained transparently.
"""
import struct
from candidate import require
CD_LIMITS={'metadata':2*1024*1024,'candidate':256*1024,'ci':64*1024,'aab':4*1024*1024,'apk':4*1024*1024}
COUNT_LIMITS={'metadata':5000,'candidate':128,'ci':4,'aab':11000,'apk':11000}
MAX_NAME=240
MAX_EXTRA=1024
MAX_COMMENT=1024
MAX_TAIL=22+65535

def preflight(stream,size,role):
 require(role in CD_LIMITS and type(size)is int and size>=22,'Invalid ZIP preflight role/size')
 def at(offset,count):
  require(type(offset)is int and type(count)is int and 0<=offset<=size and 0<=count<=MAX_TAIL and offset+count<=size,'ZIP metadata read outside bounds')
  stream.seek(offset);data=stream.read(count);require(len(data)==count,'Truncated ZIP metadata');return data
 tail_start=max(0,size-MAX_TAIL);tail=at(tail_start,size-tail_start);relative=tail.rfind(b'PK\x05\x06')
 require(relative>=0 and relative+22<=len(tail),'ZIP EOCD missing/truncated')
 eocd_offset=tail_start+relative
 sig,disk,central_disk,disk_count,count,cd_size,cd_offset,comment=struct.unpack('<4s4H2IH',tail[relative:relative+22])
 require(eocd_offset+22+comment==size,'Unsupported ZIP trailing data/comment layout')
 require(disk==central_disk==0 and disk_count==count,'Multi-disk ZIP unsupported')
 anchor=eocd_offset;is64=False
 locator=at(eocd_offset-20,20)if eocd_offset>=20 else b''
 if locator.startswith(b'PK\x06\x07'):
  _,zip64_disk,zip64_offset,disks=struct.unpack('<4sIQI',locator)
  require(zip64_disk==0 and disks==1 and 0<=zip64_offset<=eocd_offset-20-56,'ZIP64 locator outside bounds')
  record=at(zip64_offset,56)
  magic,record_size,made,needed,disk64,central_disk64,disk_count64,count64,cd_size64,cd_offset64=struct.unpack('<4sQ2H2I4Q',record)
  require(magic==b'PK\x06\x06'and record_size==44 and zip64_offset+56==eocd_offset-20,'Unsupported ZIP64 end-record layout')
  require(disk64==central_disk64==0 and disk_count64==count64,'Multi-disk ZIP64 unsupported')
  require(all(small==sentinel or small==large for small,sentinel,large in [(count,0xffff,count64),(disk_count,0xffff,disk_count64),(cd_size,0xffffffff,cd_size64),(cd_offset,0xffffffff,cd_offset64)]),'ZIP32/ZIP64 end records disagree')
  count,cd_size,cd_offset=count64,cd_size64,cd_offset64;anchor=zip64_offset;is64=True
 else:require(count!=0xffff and cd_size!=0xffffffff and cd_offset!=0xffffffff,'ZIP64 locator required for sentinel fields')
 # These gates precede directory reads and stdlib construction, even for lying EOCDs.
 require(0<count<=COUNT_LIMITS[role],'Central directory member count limit')
 require(0<cd_size<=CD_LIMITS[role],'Central directory byte limit')
 require(0<=cd_offset<anchor and cd_offset+cd_size==anchor,'Central directory offset/size inconsistent')
 cursor=cd_offset;end=anchor;seen=0;max_name=max_extra=max_comment=0
 while cursor<end:
  require(seen<count and cursor+46<=end,'Central directory member count mismatch')
  fixed=at(cursor,46);values=struct.unpack('<4s6H3I5H2I',fixed)
  require(values[0]==b'PK\x01\x02','Central directory signature mismatch')
  compressed,expanded=values[8],values[9];name_len,extra_len,comment_len,start_disk=values[10:14];local_offset=values[16]
  require(0<name_len<=MAX_NAME and extra_len<=MAX_EXTRA and comment_len<=MAX_COMMENT,'Central member metadata limit')
  next_cursor=cursor+46+name_len+extra_len+comment_len;require(next_cursor<=end,'Central member metadata overrun')
  # Fixed/individual fields only; never bulk-read a declared directory buffer.
  at(cursor+46,name_len);extra=at(cursor+46+name_len,extra_len);position=0;zip64=None
  while position<len(extra):
   require(position+4<=len(extra),'Truncated central extra field')
   tag,length=struct.unpack_from('<HH',extra,position);position+=4;require(position+length<=len(extra),'Central extra field length mismatch')
   if tag==1:require(zip64 is None,'Duplicate central ZIP64 field');zip64=extra[position:position+length]
   position+=length
  if 0xffffffff in (expanded,compressed,local_offset)or start_disk==0xffff:
   require(zip64 is not None,'Missing central ZIP64 values');position=0
   def large(width):
    nonlocal position
    require(position+width<=len(zip64),'Truncated central ZIP64 value');value=int.from_bytes(zip64[position:position+width],'little');position+=width;return value
   if expanded==0xffffffff:expanded=large(8)
   if compressed==0xffffffff:compressed=large(8)
   if local_offset==0xffffffff:local_offset=large(8)
   if start_disk==0xffff:start_disk=large(4)
  require(start_disk==0,'Central member references another disk')
  require(0<=local_offset<cd_offset and local_offset+30+name_len<=cd_offset and compressed<=cd_offset-local_offset-30-name_len,'Central member local offset/size outside payload area')
  seen+=1;cursor=next_cursor;max_name=max(max_name,name_len);max_extra=max(max_extra,extra_len);max_comment=max(max_comment,comment_len)
 require(cursor==end and seen==count,'Central directory member count mismatch')
 return {'zip64End':is64,'entries':count,'directoryBytes':cd_size,'directoryOffset':cd_offset,'maxNameBytes':max_name,'maxExtraBytes':max_extra,'maxMemberCommentBytes':max_comment,'largestPossibleRead':MAX_TAIL}
