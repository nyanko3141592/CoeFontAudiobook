import hmac
from typing import List
import os
import requests
import json
import hashlib
import re
import wave
import itertools
import datetime

from pydub import AudioSegment

import env

accesskey: str = env.accesskey
access_secret: str = env.access_secret

nobel_name: str = 'toshishun'
sentences_limit: int = 500


# テキストファイルから文章を取得
def get_text(filename):
    with open(filename, 'r', encoding='shift_jis') as f:
        text = f.read()
    return text


# テキストから一致する正規表現を削除
def del_ruby(t, *args):
    '''
    text : ルビを含む文章
    *args : ルビなどの正規表現のstrを持つlist
    '''
    for w in args:
        t = re.sub(w, '', t)
    return t


def req_api(text: str, font: str = 'Averuni', volume=3.0):
    '''
    text : 生成する文章
    font : 利用するCoeFont
    volume : 音声のvolume
    '''
    signature = hmac.new(bytes(access_secret, 'utf-8'), text.encode('utf-8'), hashlib.sha256).hexdigest()
    url = 'https://api.coefont.cloud/text2speech'

    response = requests.post(url, data=json.dumps({
        'coefont': font,
        'text': text,
        'accesskey': accesskey,
        'signature': signature,
        'volume': volume
    }), headers={'Content-Type': 'application/json'})
    return response.status_code, response.content


def join_waves(inputs, output):
    '''
    inputs : list of filenames
    output : output filename
    '''
    try:
        fps = [wave.open(f, 'r') for f in inputs]
        fpw = wave.open(output, 'w')

        fpw.setnchannels(fps[0].getnchannels())
        fpw.setsampwidth(fps[0].getsampwidth())
        fpw.setframerate(fps[0].getframerate())

        for fp in fps:
            fpw.writeframes(fp.readframes(fp.getnframes()))
            fp.close()
        fpw.close()

    except wave.Error as e:
        print(e)

    except Exception as  e:
        print('unexpected error -> ' + str(e))


os.makedirs('audiobook', exist_ok=True)
# 結合前のwavを置いとく
os.makedirs(os.path.join('audiobook', nobel_name), exist_ok=True)
# 作品の名前のwavs/nameに音声を置く
wavs_dir_path: str = os.path.join(os.path.join('audiobook', nobel_name, 'wavs'))
os.makedirs(wavs_dir_path, exist_ok=True)

text = get_text(f'text/{nobel_name}.txt')
ruby_list = ['《.+?》', '［＃１０字下げ］', '［＃.+?］', '〔.+?〕', '-{,10}']

text = del_ruby(text, *ruby_list)
print(f'文字数 {len(text)}')
sentence_list: List[str] = text.split('\n')
sentence_list = list(itertools.chain.from_iterable([s.split('。') for s in sentence_list])) + ['ボイスド　バイ コエフォントクラウド']

sentence_num: int = len(sentence_list)
fail_list: List[int] = []

with open(os.path.join(wavs_dir_path, 'sentences.json'), 'w') as f:
    json.dump(sentence_list, f, indent=2, ensure_ascii=False)

for i in range(len(sentence_list) if len(sentence_list) < 500 else sentences_limit):
    print(f'{datetime.datetime.now()} {str(i + 1).zfill(len(str(sentence_num)))}/{sentence_num} {sentence_list[i]}')
    file_name: str = f'{i}.wav'
    save_path: str = os.path.join(wavs_dir_path, file_name)
    if os.path.exists(save_path):
        continue
    if sentence_list[i] == '':
        AudioSegment.silent(duration=1000).export(save_path, 'wav')
        continue
    status, content = req_api(sentence_list[i])
    print(f'status {status}')
    if status == 200:
        with open(save_path, 'wb') as f:
            f.write(content)
    fail_list += [i]
    if status == 400:
        print('無効な文字列を含む可能性があります')

with open(os.path.join(wavs_dir_path, 'fail_sentences.json'), 'w') as f:
    json.dump(fail_list, f, indent=2, ensure_ascii=False)

out_path: str = os.path.join('audiobook', nobel_name, f'{nobel_name}.wav')

join_waves([os.path.join(wavs_dir_path, f'{i}.wav') for i in range(sentence_num) if i not in fail_list], out_path)
