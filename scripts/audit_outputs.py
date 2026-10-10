"""Extract one mid-scene frame per edit and measure the final narration loudness."""
from pathlib import Path
import json
import hashlib
import subprocess
import os
from PIL import Image

ROOT=Path(os.environ.get('F1_WORKSPACE',Path(__file__).resolve().parents[1])).resolve()

def main():
    manifest=json.loads((ROOT/'outputs/manifest.json').read_text())
    plan=json.loads((ROOT/manifest.get('edit_plan','outputs/edit-plan.json')).read_text())
    videos={v['format']:v for v in manifest['videos']}
    folder=ROOT/'outputs/qa-frames';folder.mkdir(exist_ok=True)
    audio=[]
    for fmt,scenes in plan['edits'].items():
        video_path=ROOT/videos[fmt]['path']
        frames=[]
        for i,scene in enumerate(scenes):
            out=folder/f'{fmt}-{i:02d}.jpg'
            subprocess.run(['ffmpeg','-v','error','-y','-ss',str((scene['timeline_in']+scene['timeline_out'])/2),'-i',str(video_path),'-frames:v','1',str(out)],check=True)
            im=Image.open(out).convert('RGB');im.thumbnail((240,427) if fmt=='vertical' else (512,288));frames.append(im)
        cols=7 if fmt=='vertical' else 3;rows=(len(frames)+cols-1)//cols
        sheet=Image.new('RGB',(cols*frames[0].width,rows*frames[0].height),'#09111d')
        for i,im in enumerate(frames):sheet.paste(im,((i%cols)*im.width,(i//cols)*im.height))
        sheet.save(ROOT/f'outputs/{fmt}-review-sheet.jpg')
        result=subprocess.run(['ffmpeg','-hide_banner','-i',str(video_path),'-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
        metrics,_=json.JSONDecoder().raw_decode(result.stderr[result.stderr.rfind('{'):])
        audio.append({'format':fmt,'video_sha256':hashlib.sha256(video_path.read_bytes()).hexdigest(),'measured_loudness':metrics,'status':'passed' if -19<float(metrics['input_i'])<-13 and float(metrics['input_tp'])<=-1 else 'review_required'})
    (ROOT/'outputs/audio-quality.json').write_text(json.dumps(audio,indent=2)+'\n')
    print(json.dumps(audio,indent=2))

if __name__=='__main__':main()
