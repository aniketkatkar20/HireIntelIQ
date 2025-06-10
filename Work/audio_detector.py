import pyaudio
import numpy as np
import threading
import time
import queue
import torch
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
import wave
import tempfile
import os
from datetime import datetime
import logging
import pickle
from sklearn.metrics.pairwise import cosine_similarity
import librosa
from scipy.spatial.distance import euclidean
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceRegistrationError(Exception):
    """Custom exception for voice registration errors"""
    pass

class AudioDetector:
    def __init__(self, warning_callback=None, cancel_callback=None, malpractice_callback=None):
        # Audio configuration
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.RECORD_SECONDS = 5  # Process audio in 1-second chunks
        
        # Detection parameters
        self.warning_count = 0
        self.max_warnings = 10  # Increased to 3 warnings
        self.malpractice_count = 0
        self.max_malpractice_attempts = 5
        self.is_monitoring = False
        self.is_interview_active = False
        self.audio_queue = queue.Queue()
        
        # Voice registration
        self.registered_voice_features = None
        self.is_voice_registered = False
        self.voice_similarity_threshold = 0.50  # Similarity threshold for voice matching
        self.registration_samples = []
        
        # Callbacks
        self.warning_callback = warning_callback
        self.cancel_callback = cancel_callback
        self.malpractice_callback = malpractice_callback
        
        # PyAudio instance
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
        # Silero VAD model
        self.vad_model = None
        self.load_vad_model()
        
        # Threading
        self.audio_thread = None
        self.processing_thread = None
        self.stop_event = threading.Event()
        
        # Malpractice tracking
        self.malpractice_log = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def load_vad_model(self):
        """Load Silero VAD model"""
        try:
            self.vad_model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )
            logger.info("Silero VAD model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load VAD model: {e}")
            raise
    
    def extract_voice_features(self, audio_data):
        """Extract voice features using MFCC for speaker identification"""
        try:
            # Convert to float32 and normalize
            audio_float = audio_data.astype(np.float32)
            
            # Extract MFCC features
            mfcc = librosa.feature.mfcc(
                y=audio_float, 
                sr=self.RATE, 
                n_mfcc=13,
                n_fft=2048,
                hop_length=512
            )
            
            # Calculate statistics (mean and std) for each MFCC coefficient
            mfcc_features = np.concatenate([
                np.mean(mfcc, axis=1),
                np.std(mfcc, axis=1)
            ])
            
            return mfcc_features
            
        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None
    
    def start_voice_registration(self, duration=10):
        """Start voice registration process"""
        logger.info(f"Starting voice registration for {duration} seconds...")
        
        if self.is_monitoring:
            self.stop_monitoring()
        
        self.registration_samples = []
        registration_thread = threading.Thread(
            target=self._voice_registration_loop, 
            args=(duration,)
        )
        registration_thread.daemon = True
        registration_thread.start()
        
        return registration_thread
    
    def _voice_registration_loop(self, duration):
        """Voice registration loop"""
        try:
            # Start audio stream for registration
            stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            logger.info("Recording voice sample for registration...")
            start_time = time.time()
            frames = []
            
            while time.time() - start_time < duration:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
            
            stream.stop_stream()
            stream.close()
            
            # Process recorded audio
            audio_data = b''.join(frames)
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Check for voice activity
            audio_tensor = torch.from_numpy(audio_np)
            speech_timestamps = get_speech_timestamps(
                audio_tensor, 
                self.vad_model,
                sampling_rate=self.RATE,
                threshold=0.3
            )
            
            if len(speech_timestamps) == 0:
                raise VoiceRegistrationError("No speech detected during registration")
            
            # Extract voice features from speech segments
            voice_features_list = []
            for timestamp in speech_timestamps:
                start_sample = int(timestamp['start'] * len(audio_np) / len(audio_tensor))
                end_sample = int(timestamp['end'] * len(audio_np) / len(audio_tensor))
                speech_segment = audio_np[start_sample:end_sample]
                
                if len(speech_segment) > self.RATE * 0.5:  # At least 0.5 seconds of speech
                    features = self.extract_voice_features(speech_segment)
                    if features is not None:
                        voice_features_list.append(features)
            
            if len(voice_features_list) == 0:
                raise VoiceRegistrationError("Could not extract voice features")
            
            # Calculate average features
            self.registered_voice_features = np.mean(voice_features_list, axis=0)
            self.is_voice_registered = True
            
            # Save registration data
            self._save_voice_registration()
            
            logger.info("Voice registration completed successfully")
            
        except Exception as e:
            logger.error(f"Voice registration failed: {e}")
            raise VoiceRegistrationError(f"Registration failed: {e}")
    
    def _save_voice_registration(self):
        """Save voice registration data"""
        registration_data = {
            'features': self.registered_voice_features.tolist(),
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'threshold': self.voice_similarity_threshold
        }
        
        os.makedirs('data/voice_profiles', exist_ok=True)
        with open(f'data/voice_profiles/{self.session_id}.json', 'w') as f:
            json.dump(registration_data, f, indent=2)
    
    def load_voice_registration(self, session_id):
        """Load existing voice registration"""
        try:
            with open(f'data/voice_profiles/{session_id}.json', 'r') as f:
                registration_data = json.load(f)
            
            self.registered_voice_features = np.array(registration_data['features'])
            self.is_voice_registered = True
            self.session_id = session_id
            
            logger.info(f"Voice registration loaded for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load voice registration: {e}")
            return False
    
    def verify_speaker(self, audio_data):
        """Verify if the speaker matches the registered voice"""
        if not self.is_voice_registered:
            logger.warning("No voice registered for verification")
            return False
        
        try:
            # Extract features from current audio
            features = self.extract_voice_features(audio_data)
            if features is None:
                return False
            
            # Calculate similarity with registered voice
            similarity = cosine_similarity(
                [self.registered_voice_features], 
                [features]
            )[0][0]
            
            logger.debug(f"Voice similarity: {similarity:.3f} (threshold: {self.voice_similarity_threshold})")
            
            return similarity >= self.voice_similarity_threshold
            
        except Exception as e:
            logger.error(f"Speaker verification error: {e}")
            return False
    
    def start_monitoring(self):
        """Start audio monitoring"""
        if self.is_monitoring:
            return
        
        if not self.is_voice_registered:
            raise VoiceRegistrationError("Voice must be registered before monitoring")
        
        self.is_monitoring = True
        self.stop_event.clear()
        self.warning_count = 0
        
        try:
            # Open audio stream
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Start threads
            self.audio_thread = threading.Thread(target=self._audio_capture_loop)
            self.processing_thread = threading.Thread(target=self._audio_processing_loop)
            
            self.audio_thread.daemon = True
            self.processing_thread.daemon = True
            
            self.audio_thread.start()
            self.processing_thread.start()
            
            logger.info("Audio monitoring started with speaker verification")
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            self.stop_monitoring()
            raise
    
    def stop_monitoring(self):
        """Stop audio monitoring"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.stop_event.set()
        
        # Close audio stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        # Wait for threads to finish
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2)
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2)
        
        logger.info("Audio monitoring stopped")
    
    def start_interview(self):
        """Mark interview as active"""
        self.is_interview_active = True
        self.warning_count = 0
        logger.info("Interview started - voice verification active")
    
    def end_interview(self):
        """Mark interview as inactive"""
        self.is_interview_active = False
        logger.info("Interview ended - voice verification inactive")
    
    def _audio_capture_loop(self):
        """Capture audio data in a separate thread"""
        frames = []
        frame_count = 0
        frames_per_second = self.RATE // self.CHUNK
        
        while not self.stop_event.is_set() and self.is_monitoring:
            try:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
                frame_count += 1
                
                # Process every second of audio
                if frame_count >= frames_per_second:
                    audio_data = b''.join(frames)
                    self.audio_queue.put(audio_data)
                    frames = []
                    frame_count = 0
                    
            except Exception as e:
                if self.is_monitoring:
                    logger.error(f"Audio capture error: {e}")
                break
    
    def _audio_processing_loop(self):
        """Process audio data for voice activity detection and speaker verification"""
        while not self.stop_event.is_set() and self.is_monitoring:
            try:
                # Get audio data with timeout
                try:
                    audio_data = self.audio_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Only process if interview is active
                if not self.is_interview_active:
                    continue
                
                # Convert audio data to numpy array
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Check for voice activity
                if self._detect_voice_activity(audio_np):
                    # Verify if it's the registered speaker
                    if not self.verify_speaker(audio_np):
                        self._handle_unauthorized_voice()
                
            except Exception as e:
                logger.error(f"Audio processing error: {e}")
    
    def _detect_voice_activity(self, audio_data):
        """Detect voice activity using Silero VAD"""
        try:
            # Convert to tensor
            audio_tensor = torch.from_numpy(audio_data)
            
            # Get speech timestamps
            speech_timestamps = get_speech_timestamps(
                audio_tensor, 
                self.vad_model,
                sampling_rate=self.RATE,
                threshold=0.3,
                min_speech_duration_ms=200,
                min_silence_duration_ms=100
            )
            
            # Return True if speech detected
            return len(speech_timestamps) > 0
            
        except Exception as e:
            logger.error(f"VAD detection error: {e}")
            return False
    
    def _handle_unauthorized_voice(self):
        """Handle unauthorized voice detection during interview"""
        self.warning_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Log malpractice attempt
        malpractice_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'unauthorized_voice',
            'warning_number': self.warning_count,
            'session_id': self.session_id
        }
        self.malpractice_log.append(malpractice_entry)
        
        logger.warning(f"Unauthorized voice detected! Warning {self.warning_count}/{self.max_warnings} at {timestamp}")
        
        if self.warning_callback:
            self.warning_callback(self.warning_count, self.max_warnings, 'unauthorized_voice')
        
        if self.warning_count >= self.max_warnings:
            self.malpractice_count += 1
            self._handle_malpractice_attempt()
    
    def _handle_malpractice_attempt(self):
        """Handle malpractice attempt"""
        logger.error(f"Malpractice attempt {self.malpractice_count}/{self.max_malpractice_attempts}")
        
        # Save malpractice log
        self._save_malpractice_log()
        
        if self.malpractice_callback:
            self.malpractice_callback(self.malpractice_count, self.max_malpractice_attempts)
        
        if self.malpractice_count >= self.max_malpractice_attempts:
            logger.error("Maximum malpractice attempts reached - permanently cancelling interview")
            self.is_interview_active = False
            
            # Mark candidate as blacklisted
            self._mark_candidate_blacklisted()
            
            if self.cancel_callback:
                self.cancel_callback('malpractice_limit_exceeded')
        else:
            # Reset warnings for next attempt
            self.warning_count = 0
            logger.info(f"Warnings reset. Attempt {self.malpractice_count}/{self.max_malpractice_attempts}")
    
    def _save_malpractice_log(self):
        """Save malpractice log to file"""
        os.makedirs('data/malpractice_logs', exist_ok=True)
        
        log_data = {
            'session_id': self.session_id,
            'malpractice_count': self.malpractice_count,
            'max_attempts': self.max_malpractice_attempts,
            'timestamp': datetime.now().isoformat(),
            'incidents': self.malpractice_log
        }
        
        with open(f'data/malpractice_logs/{self.session_id}.json', 'w') as f:
            json.dump(log_data, f, indent=2)
    
    def _mark_candidate_blacklisted(self):
        """Mark candidate as blacklisted due to excessive malpractice"""
        blacklist_data = {
            'session_id': self.session_id,
            'blacklisted_at': datetime.now().isoformat(),
            'reason': 'excessive_malpractice',
            'malpractice_count': self.malpractice_count,
            'incidents': len(self.malpractice_log)
        }
        
        os.makedirs('data/blacklist', exist_ok=True)
        with open(f'data/blacklist/{self.session_id}.json', 'w') as f:
            json.dump(blacklist_data, f, indent=2)
        
        logger.error(f"Candidate {self.session_id} has been blacklisted")
    
    def get_warning_count(self):
        """Get current warning count"""
        return self.warning_count
    
    def get_malpractice_count(self):
        """Get current malpractice attempt count"""
        return self.malpractice_count
    
    def reset_warnings(self):
        """Reset warning count"""
        self.warning_count = 0
        logger.info("Warning count reset")
    
    def get_malpractice_log(self):
        """Get malpractice log"""
        return self.malpractice_log
    
    def is_audio_device_available(self):
        """Check if audio input device is available"""
        try:
            device_count = self.audio.get_device_count()
            for i in range(device_count):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking audio devices: {e}")
            return False
    
    def test_voice_registration(self, duration=5):
        """Test voice registration process"""
        logger.info(f"Testing voice registration for {duration} seconds...")
        
        try:
            registration_thread = self.start_voice_registration(duration)
            registration_thread.join()  # Wait for registration to complete
            
            if self.is_voice_registered:
                logger.info("Voice registration test successful")
                return True
            else:
                logger.error("Voice registration test failed")
                return False
                
        except Exception as e:
            logger.error(f"Voice registration test error: {e}")
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_monitoring()
        if self.audio:
            self.audio.terminate()


# Example usage and testing
if __name__ == "__main__":
    def warning_handler(count, max_warnings, violation_type):
        print(f"⚠  WARNING {count}/{max_warnings}: {violation_type.replace('_', ' ').title()} detected!")
    
    def cancel_handler(reason):
        print(f"❌ INTERVIEW CANCELLED: {reason.replace('_', ' ').title()}")
    
    def malpractice_handler(count, max_attempts):
        print(f"🚨 MALPRACTICE ATTEMPT {count}/{max_attempts}: Multiple violations detected!")
    
    # Create detector
    detector = AudioDetector(
        warning_callback=warning_handler,
        cancel_callback=cancel_handler,
        malpractice_callback=malpractice_handler
    )
    
    try:
        # Check if audio device is available
        if not detector.is_audio_device_available():
            print("❌ No audio input device found!")
            exit(1)
        
        print("🎤 Enhanced Audio Detection System with Voice Registration")
        print("=" * 60)
        
        # Step 1: Voice Registration
        print("📝 Step 1: Voice Registration")
        print("Please speak clearly for 10 seconds to register your voice...")
        
        if detector.test_voice_registration(10):
            print("✅ Voice registered successfully!")
        else:
            print("❌ Voice registration failed!")
            exit(1)
        
        # Step 2: Start Monitoring
        print("\n🔍 Step 2: Starting Interview Monitoring")
        print("Only your registered voice should be detected.")
        print("Any other voice will trigger warnings...")
        
        detector.start_monitoring()
        detector.start_interview()
        
        # Test for 30 seconds
        print("Testing for 30 seconds...")
        time.sleep(30)
        
        detector.end_interview()
        detector.stop_monitoring()
        
        print(f"\n📊 Test Results:")
        print(f"   Warnings: {detector.get_warning_count()}")
        print(f"   Malpractice Attempts: {detector.get_malpractice_count()}")
        print(f"   Total Incidents: {len(detector.get_malpractice_log())}")
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        detector.cleanup()
        print("🔧 Cleanup completed")
