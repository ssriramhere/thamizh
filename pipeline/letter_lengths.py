"""Make long vowels (neṭil, 2 mātirai) twice the vowel length of their short pair (kuṟil, 1 mātirai)."""
import subprocess,sys
ONSET=0.07
PAIR={1:0,3:2,5:4,7:6,10:9,8:0,11:0}   # ā←a, ī←i, ū←u, ē←e, ō←o, ai←a, au←a
def trimmed(src,dst):
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',src,'-af','silenceremove=start_periods=1:start_threshold=-40dB,areverse,silenceremove=start_periods=1:start_threshold=-40dB,areverse','-ac','1','-ar','24000',dst],check=True)
    return float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',dst],capture_output=True,text=True).stdout)
def finish(src,dst,stretch=None):
    f=f'[0:a]atrim=0:{ONSET},asetpts=PTS-STARTPTS[a];[0:a]atrim={ONSET},asetpts=PTS-STARTPTS,rubberband=tempo={stretch}:formant=preserved[b];[a][b]concat=n=2:v=0:a=1,adelay=150:all=1,apad=pad_dur=0.15[o]' if stretch else '[0:a]adelay=150:all=1,apad=pad_dur=0.15[o]'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',src,'-filter_complex',f,'-map','[o]','-c:a','libmp3lame','-b:a','64k',dst],check=True)
def row(prefix,outprefix,voice):
    d={i:trimmed(f'{prefix}{i}-{voice}.mp3',f'/tmp/t{i}.wav') for i in range(12)}
    out={}
    for i in range(12):
        if i in PAIR:
            s=d[PAIR[i]]; target=ONSET+2*max(0.08,s-ONSET)
            tempo=(d[i]-ONSET)/(target-ONSET)
            if tempo<0.97 or tempo>1.1:
                finish(f'/tmp/t{i}.wav',f'{outprefix}{i}-{voice}.mp3',min(2.0,max(0.2,round(tempo,3)))); out[i]=round(target,3); continue
        finish(f'/tmp/t{i}.wav',f'{outprefix}{i}-{voice}.mp3'); out[i]=round(d[i],3)
    return d,out
if __name__=='__main__':
    for v in ('Orus','Aoede'):
        d,o=row(sys.argv[1],sys.argv[2],v); print(v,[round(d[i],2) for i in range(12)],'->',[o[i] for i in range(12)])
