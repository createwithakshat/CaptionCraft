import { useState, useRef } from 'react';
import { Upload, FileAudio, Copy, Download, Sparkles, Loader2, CheckCircle, AlertCircle, Play, Pause, SkipBack, SkipForward, Video, Mic, FileText, Wand2 } from 'lucide-react';

const API_BASE_URL = 'https://captioncraft-cal6.onrender.com';

const VTTGenerator = () => {
  const [audioFile, setAudioFile] = useState(null);
  const [fileId, setFileId] = useState(null);
  const [fileType, setFileType] = useState(null);
  const [mode, setMode] = useState('manual'); // 'manual' or 'auto'
  const [transcript, setTranscript] = useState('');
  const [cleanedTranscript, setCleanedTranscript] = useState('');
  const [isCleaned, setIsCleaned] = useState(false);
  const [vttOutput, setVttOutput] = useState('');
  const [segments, setSegments] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCleaning, setIsCleaning] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [notification, setNotification] = useState({ show: false, type: '', message: '' });
  
  // Audio player states
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [currentCaption, setCurrentCaption] = useState(null);
  const [activeCaptionIndex, setActiveCaptionIndex] = useState(-1);
  
  const fileInputRef = useRef(null);
  const audioRef = useRef(null);
  const captionRefs = useRef([]);

  const showNotification = (type, message) => {
    setNotification({ show: true, type, message });
    setTimeout(() => setNotification({ show: false, type: '', message: '' }), 3000);
  };

  // Update current caption based on audio time
  const updateCurrentCaption = (time) => {
    if (!segments || segments.length === 0) return;
    
    const activeIndex = segments.findIndex(
      seg => time >= seg.start && time <= seg.end
    );
    
    if (activeIndex !== activeCaptionIndex) {
      setActiveCaptionIndex(activeIndex);
      setCurrentCaption(activeIndex !== -1 ? segments[activeIndex] : null);
      
      if (activeIndex !== -1 && captionRefs.current[activeIndex]) {
        captionRefs.current[activeIndex].scrollIntoView({
          behavior: 'smooth',
          block: 'center'
        });
      }
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      const time = audioRef.current.currentTime;
      setCurrentTime(time);
      updateCurrentCaption(time);
    }
  };

  const seekToCaption = (startTime) => {
    if (audioRef.current) {
      audioRef.current.currentTime = startTime;
      setCurrentTime(startTime);
      if (!isPlaying) {
        audioRef.current.play();
        setIsPlaying(true);
      }
      updateCurrentCaption(startTime);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const videoExtensions = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'm4v'];
    const audioExtensions = ['mp3', 'wav', 'm4a', 'ogg', 'flac'];
    const fileExt = file.name.split('.').pop().toLowerCase();
    
    const isVideo = videoExtensions.includes(fileExt);
    const isAudio = audioExtensions.includes(fileExt);
    
    if (!isVideo && !isAudio) {
      showNotification('error', 'Please upload an audio or video file');
      return;
    }

    setAudioFile(file);
    setFileType(isVideo ? 'video' : 'audio');
    setIsUploading(true);
    setUploadProgress(0);
    
    // Reset all states
    setTranscript('');
    setCleanedTranscript('');
    setIsCleaned(false);
    setVttOutput('');
    setSegments([]);
    setFileId(null);
    setCurrentCaption(null);
    setActiveCaptionIndex(-1);
    setIsPlaying(false);
    if (audioRef.current) {
      audioRef.current.pause();
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const interval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(interval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      const response = await fetch(`${API_BASE_URL}/upload-file`, {
        method: 'POST',
        body: formData,
      });

      clearInterval(interval);
      setUploadProgress(100);

      if (!response.ok) throw new Error('Upload failed');

      const data = await response.json();
      setFileId(data.file_id);
      showNotification('success', `${data.type === 'video' ? 'Video' : 'Audio'} uploaded! Now choose your method.`);
      
    } catch (error) {
      console.error('Upload error:', error);
      showNotification('error', 'Failed to upload file');
    } finally {
      setIsUploading(false);
      setTimeout(() => setUploadProgress(0), 1000);
    }
  };

  const handleAutoTranscribe = async () => {
    if (!fileId) {
      showNotification('error', 'Please upload a file first');
      return;
    }

    setIsTranscribing(true);
    const formData = new FormData();
    formData.append('file_id', fileId);

    try {
      const response = await fetch(`${API_BASE_URL}/auto-transcribe`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Transcription failed');

      const data = await response.json();
      setTranscript(data.transcript);
      setCleanedTranscript(data.cleaned_transcript);
      setIsCleaned(true);
      showNotification('success', '✅ Auto-transcription completed! Ready to generate captions.');
      setVttOutput('');
      setSegments([]);
      
    } catch (error) {
      console.error('Transcription error:', error);
      showNotification('error', 'Failed to transcribe audio');
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleCleanTranscript = async () => {
    if (!transcript.trim()) {
      showNotification('error', 'Please enter a transcript first');
      return;
    }

    setIsCleaning(true);
    const formData = new FormData();
    formData.append('transcript', transcript);

    try {
      const response = await fetch(`${API_BASE_URL}/clean-transcript`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Cleaning failed');

      const data = await response.json();
      setCleanedTranscript(data.cleaned);
      setIsCleaned(true);
      showNotification('success', 'Transcript cleaned! Ready to generate captions.');
      setVttOutput('');
      setSegments([]);
      
    } catch (error) {
      console.error('Clean error:', error);
      showNotification('error', 'Failed to clean transcript');
      setIsCleaned(false);
    } finally {
      setIsCleaning(false);
    }
  };

  const handleGenerateVTT = async () => {
    if (!isCleaned || !cleanedTranscript) {
      showNotification('error', 'Please prepare transcript first (manual or auto)');
      return;
    }

    if (!fileId) {
      showNotification('error', 'Please upload a file first');
      return;
    }

    setIsGenerating(true);
    const formData = new FormData();
    formData.append('file_id', fileId);
    formData.append('cleaned_transcript', cleanedTranscript);

    try {
      const response = await fetch(`${API_BASE_URL}/generate-vtt`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Generation failed');
      }

      const data = await response.json();
      setVttOutput(data.vtt);
      setSegments(data.segments);
      showNotification('success', data.message);
      
      setCurrentCaption(null);
      setActiveCaptionIndex(-1);
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
      }
      
    } catch (error) {
      console.error('Generation error:', error);
      showNotification('error', error.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyVTT = () => {
    if (!vttOutput) {
      showNotification('error', 'Nothing to copy yet');
      return;
    }
    navigator.clipboard.writeText(vttOutput);
    showNotification('success', 'VTT copied to clipboard!');
  };

  const handleDownloadVTT = () => {
    if (!vttOutput) {
      showNotification('error', 'Nothing to download yet');
      return;
    }
    const blob = new Blob([vttOutput], { type: 'text/vtt' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'captions.vtt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showNotification('success', 'VTT file downloaded!');
  };

  const togglePlayPause = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleTranscriptChange = (e) => {
    setTranscript(e.target.value);
    if (isCleaned) {
      setIsCleaned(false);
      setCleanedTranscript('');
      setVttOutput('');
      setSegments([]);
      setMode('manual');
    }
  };

  const formatTimePreview = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Notification */}
      {notification.show && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg animate-slide-in ${
          notification.type === 'success' ? 'bg-green-500' : notification.type === 'error' ? 'bg-red-500' : 'bg-blue-500'
        } text-white`}>
          {notification.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
          <span>{notification.message}</span>
        </div>
      )}

      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
        <div className="inline-block">
        <h1 className="text-6xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent mb-2">
          CaptionCraft
        </h1>
        <p className="text-xs text-gray-500 tracking-wider mt-1">™</p>
      </div>
      <p className="text-gray-300 text-lg mt-4">Create perfectly synchronized captions for audio & video</p>
    </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Left Column */}
          <div className="space-y-6">
            {/* File Upload Card */}
            <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                {fileType === 'video' ? <Video size={24} /> : <FileAudio size={24} />}
                Upload {fileType === 'video' ? 'Video' : 'Audio'}
              </h2>
              
              <div
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                  audioFile ? 'border-green-400 bg-green-400/10' : 'border-white/30 hover:border-purple-400 bg-white/5'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mp3,.wav,.m4a,.ogg,.flac,.mp4,.mov,.avi,.mkv,.webm"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                
                {isUploading ? (
                  <div className="space-y-4">
                    <Loader2 className="animate-spin mx-auto text-purple-400" size={48} />
                    <p className="text-white">Uploading... {uploadProgress}%</p>
                    <div className="w-full bg-white/20 rounded-full h-2 overflow-hidden">
                      <div 
                        className="bg-gradient-to-r from-purple-400 to-pink-400 h-full transition-all duration-300"
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                  </div>
                ) : audioFile ? (
                  <div className="space-y-2">
                    <CheckCircle className="mx-auto text-green-400" size={48} />
                    <p className="text-green-400 font-semibold">{audioFile.name}</p>
                    <p className="text-gray-300 text-sm">
                      {fileType === 'video' ? '🎬 Video file (audio extracted)' : '🎵 Audio file'}
                    </p>
                    <p className="text-gray-300 text-sm">Click to change file</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Upload className="mx-auto text-gray-400" size={48} />
                    <p className="text-gray-300">Click or drag to upload</p>
                    <p className="text-gray-400 text-sm">🎵 Audio: MP3, WAV, M4A, OGG, FLAC</p>
                    <p className="text-gray-400 text-sm">🎬 Video: MP4, MOV, AVI, MKV, WEBM</p>
                  </div>
                )}
              </div>

              {/* Audio Player */}
              {fileId && audioFile && (
                <div className="mt-4 p-4 bg-black/50 rounded-lg">
                  <audio
                    ref={audioRef}
                    src={`${API_BASE_URL}/get-audio/${fileId}`}
                    onTimeUpdate={handleTimeUpdate}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    className="w-full"
                    controls
                  />
                </div>
              )}
            </div>

            {/* Mode Selection Card */}
            {fileId && !isCleaned && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                <h2 className="text-xl font-semibold text-white mb-4">Choose Method</h2>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => setMode('manual')}
                    className={`p-4 rounded-xl transition-all ${
                      mode === 'manual'
                        ? 'bg-gradient-to-r from-purple-600 to-pink-600 border-2 border-white'
                        : 'bg-white/10 hover:bg-white/20 border-2 border-transparent'
                    }`}
                  >
                    <FileText className="mx-auto mb-2" size={32} />
                    <p className="text-white font-semibold">Manual</p>
                    <p className="text-gray-400 text-sm">Paste your transcript</p>
                  </button>
                  
                  <button
                    onClick={() => setMode('auto')}
                    className={`p-4 rounded-xl transition-all ${
                      mode === 'auto'
                        ? 'bg-gradient-to-r from-purple-600 to-pink-600 border-2 border-white'
                        : 'bg-white/10 hover:bg-white/20 border-2 border-transparent'
                    }`}
                  >
                    <Wand2 className="mx-auto mb-2" size={32} />
                    <p className="text-white font-semibold">AI Auto</p>
                    <p className="text-gray-400 text-sm">Auto-transcribe with AI</p>
                  </button>
                </div>
              </div>
            )}

            {/* Transcript Card (Manual Mode) */}
            {mode === 'manual' && fileId && !isCleaned && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                <h2 className="text-xl font-semibold text-white mb-4">📝 Enter Transcript</h2>
                
                <textarea
                  value={transcript}
                  onChange={handleTranscriptChange}
                  placeholder="Paste or type your transcript here..."
                  className="w-full h-64 bg-white/5 border border-white/20 rounded-lg p-4 text-white placeholder-gray-400 focus:outline-none focus:border-purple-400 resize-none"
                />
                
                <button
                  onClick={handleCleanTranscript}
                  disabled={isCleaning || !transcript.trim()}
                  className="mt-4 w-full py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:cursor-not-allowed rounded-lg text-white font-semibold transition-all flex items-center justify-center gap-2"
                >
                  {isCleaning ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Sparkles size={20} />
                      Process Transcript
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Auto Mode Card */}
            {mode === 'auto' && fileId && !isCleaned && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                <h2 className="text-xl font-semibold text-white mb-4">🤖 AI Auto-Transcription</h2>
                <p className="text-gray-300 mb-4">
                  Let AI listen to your audio and generate the transcript automatically.
                  Powered by Whisper AI.
                </p>
                
                <button
                  onClick={handleAutoTranscribe}
                  disabled={isTranscribing}
                  className="w-full py-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white font-semibold transition-all flex items-center justify-center gap-2"
                >
                  {isTranscribing ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      Transcribing Audio...
                    </>
                  ) : (
                    <>
                      <Mic size={20} />
                      Start Auto-Transcription
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Ready State */}
            {isCleaned && (
              <div className="bg-green-500/20 backdrop-blur-lg rounded-2xl p-6 border border-green-500/30">
                <CheckCircle className="mx-auto text-green-400 mb-2" size={48} />
                <p className="text-green-300 text-center font-semibold">✓ Transcript Ready!</p>
                <p className="text-gray-300 text-center text-sm mt-2">
                  {mode === 'auto' ? 'AI transcribed' : 'Manual transcript'} is processed and ready
                </p>
              </div>
            )}
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Generate Button */}
            <button
              onClick={handleGenerateVTT}
              disabled={isGenerating || !fileId || !isCleaned}
              className={`w-full py-4 rounded-xl text-white font-bold text-lg transition-all transform flex items-center justify-center gap-3 ${
                isGenerating || !fileId || !isCleaned
                  ? 'bg-gray-600 cursor-not-allowed opacity-50'
                  : 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 hover:scale-105'
              }`}
            >
              {isGenerating ? (
                <>
                  <Loader2 className="animate-spin" size={24} />
                  Generating Captions...
                </>
              ) : (
                <>
                  <Sparkles size={24} />
                  Generate VTT Captions
                </>
              )}
            </button>

            {/* Live Caption Preview */}
            {segments.length > 0 && (
              <div className="bg-gradient-to-r from-purple-600/20 to-pink-600/20 backdrop-blur-lg rounded-2xl p-6 border border-purple-500/30">
                <h2 className="text-xl font-semibold text-white mb-4">🎤 Live Caption</h2>
                <div className="bg-black/50 rounded-lg p-6 text-center min-h-[120px] flex items-center justify-center">
                  {currentCaption ? (
                    <p className="text-2xl font-bold text-transparent bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text">
                      {currentCaption.text}
                    </p>
                  ) : (
                    <p className="text-gray-400 text-lg">Play audio to see live captions</p>
                  )}
                </div>
                <div className="flex justify-center gap-4 mt-4">
                  <button
                    onClick={() => {
                      if (audioRef.current) {
                        audioRef.current.currentTime = Math.max(0, currentTime - 5);
                      }
                    }}
                    className="p-2 bg-white/10 hover:bg-white/20 rounded-full transition-all"
                  >
                    <SkipBack size={20} />
                  </button>
                  <button
                    onClick={togglePlayPause}
                    className="p-3 bg-purple-600 hover:bg-purple-700 rounded-full transition-all"
                  >
                    {isPlaying ? <Pause size={24} /> : <Play size={24} />}
                  </button>
                  <button
                    onClick={() => {
                      if (audioRef.current) {
                        audioRef.current.currentTime = Math.min(audioRef.current.duration, currentTime + 5);
                      }
                    }}
                    className="p-2 bg-white/10 hover:bg-white/20 rounded-full transition-all"
                  >
                    <SkipForward size={20} />
                  </button>
                </div>
              </div>
            )}

            {/* Captions List */}
            {segments.length > 0 && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                <h2 className="text-xl font-semibold text-white mb-4">📜 All Captions ({segments.length})</h2>
                <div className="h-80 overflow-y-auto space-y-2">
                  {segments.map((seg, idx) => (
                    <div
                      key={idx}
                      ref={el => captionRefs.current[idx] = el}
                      onClick={() => seekToCaption(seg.start, idx)}
                      className={`p-3 rounded-lg cursor-pointer transition-all ${
                        activeCaptionIndex === idx
                          ? 'bg-gradient-to-r from-purple-600 to-pink-600 border-l-4 border-white'
                          : 'bg-white/5 hover:bg-white/10 border-l-4 border-transparent'
                      }`}
                    >
                      <div className="text-xs text-gray-400 mb-1">
                        {formatTimePreview(seg.start)} → {formatTimePreview(seg.end)}
                      </div>
                      <div className={`text-sm ${activeCaptionIndex === idx ? 'text-white font-semibold' : 'text-gray-300'}`}>
                        {seg.text}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* VTT Actions */}
            {vttOutput && (
              <div className="flex gap-3">
                <button
                  onClick={handleCopyVTT}
                  className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-semibold transition-all flex items-center justify-center gap-2"
                >
                  <Copy size={20} />
                  Copy VTT
                </button>
                <button
                  onClick={handleDownloadVTT}
                  className="flex-1 py-3 bg-green-600 hover:bg-green-700 rounded-lg text-white font-semibold transition-all flex items-center justify-center gap-2"
                >
                  <Download size={20} />
                  Download VTT
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        .animate-slide-in {
          animation: slide-in 0.3s ease-out;
        }
      `}</style>

            {/* Footer */}
      <footer className="mt-16 pt-8 border-t border-white/10">
        <div className="text-center">
          <p className="text-gray-400 text-sm">
            © 2026 Akshat Aswal. All rights reserved.
          </p>
          <p className="text-gray-500 text-xs mt-1">
            Made with 🎤 for perfectly synchronized captions
          </p>
        </div>
      </footer>

    </div>
  );
};

export default VTTGenerator;