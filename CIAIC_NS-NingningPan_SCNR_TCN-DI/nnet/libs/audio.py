# wujian@2018

import optparse
import numpy as np
import scipy.io.wavfile as wf
# import librosa
import os

MAX_INT16 = np.iinfo(np.int16).max


def write_wav(fname, samps, fs=16000, normalize=True):
    """
    Write wav files in int16, support single/multi-channel
    """
    if normalize:
        samps = samps * MAX_INT16
    # scipy.io.wavfile.write could write single/multi-channel files
    # for multi-channel, accept ndarray [Nsamples, Nchannels]
    if samps.ndim != 1 and samps.shape[0] < samps.shape[1]:
        samps = np.transpose(samps)
        samps = np.squeeze(samps)
    # same as MATLAB and kaldi
    samps_int16 = samps.astype(np.int16)
    fdir = os.path.dirname(fname)
    if fdir and not os.path.exists(fdir):
        os.makedirs(fdir)
    # NOTE: librosa 0.6.0 seems could not write non-float narray
    #       so use scipy.io.wavfile instead
    wf.write(fname, fs, samps_int16)


def read_wav(fname, normalize=True, return_rate=False):
    """
    Read wave files using scipy.io.wavfile(support multi-channel)
    """
    # samps_int16: N x C or N
    #   N: number of samples
    #   C: number of channels
    samp_rate, samps_int16 = wf.read(fname)
    # N x C => C x N
    samps = samps_int16.astype(np.float)
    # tranpose because I used to put channel axis first
    if samps.ndim != 1:
        samps = np.transpose(samps)
    # normalize like MATLAB and librosa
    if normalize:
        samps = samps / MAX_INT16
    if return_rate:
        return samp_rate, samps
    return samps


def parse_scripts(scp_path, value_processor=lambda x: x, num_tokens=2):
    """
    Parse kaldi's script(.scp) file
    If num_tokens >= 2, function will check token number
    """
    scp_dict = dict()
    line = 0
    with open(scp_path, "r") as f:
        for raw_line in f:
            scp_tokens = raw_line.strip().split()
            line += 1
            if num_tokens >= 2 and len(scp_tokens) != num_tokens or len(
                    scp_tokens) < 2:
                raise RuntimeError(
                    "For {}, format error in line[{:d}]: {}".format(
                        scp_path, line, raw_line))
            if num_tokens == 2:
                key, value = scp_tokens
            else:
                key, value = scp_tokens[0], scp_tokens[1:]
            if key in scp_dict:
                raise ValueError("Duplicated key \'{0}\' exists in {1}".format(
                    key, scp_path))
            scp_dict[key] = value_processor(value)
    return scp_dict


class Reader(object):
    """
        Basic Reader Class
    """
# python中所有的迭代环境都会先尝试__iter__方法，再尝试__getitem__
# 看到__iter__就是一个迭代器，看到yield就是一个generator，__iter__可以配合__next__使用。yield配合万物……一个函数加个yield就成了生成器，生成器是一个elegant的迭代器。遇到return终止迭代。
# 一个class中有__iter__  __next__ yield，这个class就是个被改造了的迭代器。


    def __init__(self, scp_path, value_processor=lambda x: x):
        self.index_dict = parse_scripts(
            scp_path, value_processor=value_processor, num_tokens=2)
        self.index_keys = list(self.index_dict.keys())

    def _load(self, key):
        # return path
        return self.index_dict[key]

    # number of utterance
    def __len__(self):
        return len(self.index_dict)

    # avoid key error
    def __contains__(self, key):
        return key in self.index_dict
    
    
    # sequential index
    def __iter__(self):
        for key in self.index_keys:
            yield key, self._load(key)  # 见到yield就见到生成器

    # random index, support str/int as index
    def __getitem__(self, index):
        if type(index) not in [int, str]:
            raise IndexError("Unsupported index type: {}".format(type(index)))
        if type(index) == int:
            # from int index to key
            num_utts = len(self.index_keys)
            if index >= num_utts or index < 0:
                raise KeyError(
                    "Interger index out of range, {:d} vs {:d}".format(
                        index, num_utts))
            index = self.index_keys[index]
        if index not in self.index_dict:
            raise KeyError("Missing utterance {}!".format(index))
        return self._load(index)


class WaveReader(Reader):
    """
        Sequential/Random Reader for single channel wave
        Format of wav.scp follows Kaldi's definition:
            key1 /path/to/wav
            ...
    """

    def __init__(self, wav_scp, sample_rate=None, normalize=True):
        super(WaveReader, self).__init__(wav_scp)
        self.samp_rate = sample_rate
        self.normalize = normalize

    def _load(self, key):
        # return C x N or N
        samp_rate, samps = read_wav(
            self.index_dict[key], normalize=self.normalize, return_rate=True)
        # if given samp_rate, check it
        if self.samp_rate is not None and samp_rate != self.samp_rate:
#             samps = librosa.resample(samps, orig_sr=samp_rate, target_sr=self.samp_rate)
            raise RuntimeError("SampleRate mismatch: {:d} vs {:d}".format(
                samp_rate, self.samp_rate))
        return samps