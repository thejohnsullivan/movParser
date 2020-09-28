import argparse
import struct

""" Change the framerate of a mov file """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('filename',
                    help='filename to change framerate')
parser.add_argument('framerate', type=float,
                    help='new frame rate')
parser.parse_args()
args = parser.parse_args()

ATOM_HEADER_SIZE = 8



def readAtomDataFromFile(file, atomID):
    atom_header = f.read(ATOM_HEADER_SIZE)
    while atom_header:
        if len(atom_header) == 0:
            break
        print('atom header:', atom_header)  # debug purposes
        atom_size = struct.unpack('>I', atom_header[0:4])[0]
        if atom_header[4:8] == atomID:
            return atom_header + f.read(atom_size - ATOM_HEADER_SIZE)
        else:
            f.seek(atom_size - ATOM_HEADER_SIZE, 1)
        atom_header = f.read(ATOM_HEADER_SIZE)
    raise RuntimeError('expected to find {} header.'.format(atomID))

atomsWithSubs = [
        b'moov',
        b'trak',
        b'mdia',
        b'minf',
        b'stbl',
        b'dinf',
        b'clip',
        b'udta',
        b'matt',
        b'edts',
        ]

def dictifyAtom(data):
    index = ATOM_HEADER_SIZE
    atomDict = dict()
    while index < len(data):
        atom_header = data[index:index+ATOM_HEADER_SIZE]
        #print('atom header:', atom_header)  # debug purposes
        atom_size = struct.unpack('>I', atom_header[0:4])[0]
        atom_id = atom_header[4:8]
        atom_id_count = 0
        for key in atomDict.keys():
            if key[0] == atom_id:
                atom_id_count += 1
        if atom_id in atomsWithSubs:
            # print("entering {}".format(atom_id))
            atomDict[atom_id,atom_id_count] = dictifyAtom(data[index:index+atom_size])
        else:
            atomDict[atom_id,atom_id_count] = data[index+ATOM_HEADER_SIZE:index+atom_size]
        index += atom_size
    return atomDict

def printAtomDict(d,tabs=''):
    if not isinstance(d,dict):
        return
    for key in d.keys():
        print(tabs+str(key))
        if key[0] in atomsWithSubs:
            printAtomDict(d[key],'  '+tabs)

def atomDictToBytes(atomDict):
    ret = b''
    #print('keys: {}'.format(atomDict.keys()))
    for key in atomDict.keys():
        #print('key: {}'.format(key))  # debug purposes
        #print('atom: "{}"'.format(atomDict[key]))
        if key[0] in atomsWithSubs:
            tmp = atomDictToBytes(atomDict[key])
            ret += struct.pack('>I',len(tmp)+ATOM_HEADER_SIZE)+key[0]
            ret += tmp
        else:
            ret += struct.pack('>I',len(atomDict[key])+ATOM_HEADER_SIZE)+key[0]
            ret += atomDict[key]
    return ret

def getSubAtom(data, atomID):
    index = ATOM_HEADER_SIZE
    while index < len(data):
        atom_header = data[index:index+ATOM_HEADER_SIZE]
        print('atom header:', atom_header)  # debug purposes
        atom_size = struct.unpack('>I', atom_header[0:4])[0]
        if atom_header[4:8] == atomID:
            return data[index:index+atom_size]
        else:
            index += atom_size
    raise RuntimeError('expected to find {} header.'.format(atomID))

# search for moov item
with open(args.filename, "r+") as f:

    moov = readAtomDataFromFile(f, b'moov')

    atomDict = dictifyAtom(moov)
    print(atomDict)
    printAtomDict(atomDict)

    # trak = getSubAtom(moov, b'trak')
    # mdia = getSubAtom(trak, b'mdia')
    # mdhd = getSubAtom(mdia, b'mdhd')
    # minf = getSubAtom(mdia, b'minf')
    # stbl = getSubAtom(minf, b'stbl')
    # stts = getSubAtom(stbl, b'stts')
    try:
        mdhd_data = atomDict['trak',0]['mdia',0]['mdhd',0]
    except:
        raise RuntimeError('expected to find "mdhd" header.')
    print("atom of length {}".format(len(mdhd_data)))
    version, flags,flags2, creationTime, \
            modTime, timeScale, duration, \
            lang, quality = struct.unpack('>BHBIIIIHH',mdhd_data[0:24])
    print("Found timescale of {}".format(timeScale))
    print("Found duration of {}".format(duration))
    newTimeScale = args.framerate*1000
    newDuration = int(float(duration) * (float(timeScale)/float(newTimeScale)))
    print("New timescale of {}".format(newTimeScale))
    print("New duration of {}".format(newDuration))
    mdhd_data = struct.pack('>BHBIIIIHH',version, flags,flags2, creationTime, \
                                        modTime, newTimeScale, newDuration, \
                                        lang, quality)
    atomDict['trak',0]['mdia',0]['mdhd',0] = mdhd_data

    try:
        mvhd_data = atomDict['mvhd',0]
    except:
        raise RuntimeError('expected to find "mvhd" header.')
    print("atom of length {}".format(len(mvhd_data)))
    version, flags,flags2, creationTime, \
            modTime, timeScale, duration, \
            prefRate, prefVolume = struct.unpack('>BHBIIIIII',mvhd_data[0:28])
    mvhd_data_remainder = mvhd_data[28:]
    print("Found timescale of {}".format(timeScale))
    print("Found duration of {}".format(duration))
    newTimeScale = args.framerate*1000
    newDuration = int(float(duration) * (float(timeScale)/float(newTimeScale)))
    print("New timescale of {}".format(newTimeScale))
    print("New duration of {}".format(newDuration))
    mvhd_data = struct.pack('>BHBIIIIII',version, flags,flags2, creationTime, \
                                         modTime, newTimeScale, newDuration, \
                                         prefRate, prefVolume) + mvhd_data_remainder
    atomDict['mvhd',0] = mvhd_data

    try:
        stts_data = atomDict['trak',0]['mdia',0]['minf',0]['stbl',0]['stts',0]
    except:
        raise RuntimeError('expected to find "stts" header.')
    version, flags,flags2, numEntries = struct.unpack('>BHBI',stts_data[0:8])
    if numEntries > 1:
        raise RuntimeError('expected only one framerate')
    sampleCount, sampleDuration = struct.unpack('>II',stts_data[8:16])
    print("Found {} samples and {} duration".format(sampleCount,sampleDuration))
    print("Found framerate of {} fps".format((float(timeScale)/float(sampleDuration))))
    newDuration = int(float(timeScale) / args.framerate)
    print("Writing new duration of {}".format(newDuration))
    stts_data = stts_data[:12]
    stts_data += struct.pack('>I', newDuration)
    atomDict['trak',0]['mdia',0]['minf',0]['stbl',0]['stts',0] = stts_data

    f.seek(-len(moov), 1) # go back to the beginning of moov
    atoms = atomDictToBytes(atomDict)
    newMoov = struct.pack('>I',len(atoms)+ATOM_HEADER_SIZE)+b'moov'
    newMoov += atoms
    print('newMoov len {}, vs old {}'.format(len(newMoov),len(moov)))
    f.write(newMoov)
    f.close()
