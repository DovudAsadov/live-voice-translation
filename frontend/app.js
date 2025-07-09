class VoiceTranslator {
    constructor() {
        this.socket = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.isConnected = false;
        this.currentRoom = null;
        this.userLanguage = 'en';
        this.audioContext = null;
        this.analyser = null;
        this.microphone = null;
        this.volumeUpdateInterval = null;
        
        this.initializeElements();
        this.setupEventListeners();
        this.requestMicrophonePermission();
    }
    
    initializeElements() {
        this.elements = {
            setupSection: document.getElementById('setupSection'),
            controlSection: document.getElementById('controlSection'),
            roomId: document.getElementById('roomId'),
            userLanguage: document.getElementById('userLanguage'),
            serverUrl: document.getElementById('serverUrl'),
            connectBtn: document.getElementById('connectBtn'),
            disconnectBtn: document.getElementById('disconnectBtn'),
            status: document.getElementById('status'),
            micButton: document.getElementById('micButton'),
            conversation: document.getElementById('conversation'),
            loading: document.getElementById('loading'),
            error: document.getElementById('error'),
            currentRoom: document.getElementById('currentRoom'),
            userCount: document.getElementById('userCount'),
            usersList: document.getElementById('usersList'),
            volumeBar: document.getElementById('volumeBar')
        };
    }
    
    setupEventListeners() {
        this.elements.connectBtn.addEventListener('click', () => this.connectToRoom());
        this.elements.disconnectBtn.addEventListener('click', () => this.disconnect());
        
        // Mouse events for desktop
        this.elements.micButton.addEventListener('mousedown', () => this.startRecording());
        this.elements.micButton.addEventListener('mouseup', () => this.stopRecording());
        this.elements.micButton.addEventListener('mouseleave', () => this.stopRecording());
        
        // Touch events for mobile
        this.elements.micButton.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.startRecording();
        });
        this.elements.micButton.addEventListener('touchend', (e) => {
            e.preventDefault();
            this.stopRecording();
        });
        
        // Keyboard shortcut (spacebar)
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && !this.isRecording && this.isConnected) {
                e.preventDefault();
                this.startRecording();
            }
        });
        
        document.addEventListener('keyup', (e) => {
            if (e.code === 'Space' && this.isRecording) {
                e.preventDefault();
                this.stopRecording();
            }
        });
    }
    
    async requestMicrophonePermission() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.setupAudioContext(stream);
            this.showStatus('Microphone access granted', 'connected');
        } catch (error) {
            this.showError('Microphone access denied. Please allow microphone access to use voice translation.');
        }
    }
    
    setupAudioContext(stream) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        this.analyser = this.audioContext.createAnalyser();
        this.microphone = this.audioContext.createMediaStreamSource(stream);
        this.microphone.connect(this.analyser);
        this.analyser.fftSize = 256;
        
        this.startVolumeMonitoring();
    }
    
    startVolumeMonitoring() {
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        
        const updateVolume = () => {
            if (this.analyser) {
                this.analyser.getByteFrequencyData(dataArray);
                const average = dataArray.reduce((a, b) => a + b) / bufferLength;
                const volumePercent = (average / 128) * 100;
                this.elements.volumeBar.style.width = `${volumePercent}%`;
                
                if (this.isConnected) {
                    requestAnimationFrame(updateVolume);
                }
            }
        };
        
        updateVolume();
    }
    
    connectToRoom() {
        const roomId = this.elements.roomId.value.trim();
        const serverUrl = this.elements.serverUrl.value.trim();
        
        if (!roomId) {
            this.showError('Please enter a room ID');
            return;
        }
        
        this.userLanguage = this.elements.userLanguage.value;
        
        this.showLoading(true);
        this.hideError();
        
        try {
            this.socket = io(serverUrl, {
                reconnectionAttempts: 3,
                timeout: 5000
            });
            this.setupSocketListeners();

            this.socket.on('connect', () => {
                console.log('Socket.IO connected to', serverUrl);
                this.socket.emit('join_room', {
                    room_id: roomId,
                    language: this.userLanguage
                });
            });

            this.socket.on('connect_error', (err) => {
                console.error('Socket.IO connection error:', err);
                this.showError('Failed to connect to server. Please check the server URL and that the backend is running.');
                this.showLoading(false);
            });

            this.socket.on('connect_timeout', () => {
                console.error('Socket.IO connection timed out');
                this.showError('Connection to server timed out.');
                this.showLoading(false);
            });
        } catch (error) {
            this.showError('Failed to connect to server. Please check the server URL.');
            this.showLoading(false);
        }
    }
    
    setupSocketListeners() {
        this.socket.on('connected', (data) => {
            console.log('Connected to server:', data.message);
        });
        
        this.socket.on('room_joined', (data) => {
            this.currentRoom = data.room_id;
            this.isConnected = true;
            this.showLoading(false);
            this.showControlSection();
            this.elements.currentRoom.textContent = this.currentRoom;
            this.elements.userCount.textContent = data.users_count;
            this.showStatus('Connected to room', 'connected');
        });
        
        this.socket.on('user_joined', (data) => {
            this.elements.userCount.textContent = data.room_users;
            this.addMessage('system', `User joined (${data.language})`);
            this.updateUsersList();
        });
        
        this.socket.on('user_left', (data) => {
            this.addMessage('system', 'User left the room');
            this.updateUsersList();
        });
        
        this.socket.on('translated_audio', (data) => {
            this.handleTranslatedAudio(data);
        });
        
        this.socket.on('error', (data) => {
            this.showError(data.message);
        });
        
        this.socket.on('disconnect', () => {
            this.isConnected = false;
            this.showStatus('Disconnected from server');
            this.showError('Connection lost. Please reconnect.');
        });
    }
    
    showControlSection() {
        this.elements.setupSection.style.display = 'none';
        this.elements.controlSection.style.display = 'block';
    }
    
    showSetupSection() {
        this.elements.setupSection.style.display = 'block';
        this.elements.controlSection.style.display = 'none';
    }
    
    async startRecording() {
        if (this.isRecording || !this.isConnected) return;
        
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000
                }
            });
            
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            this.audioChunks = [];
            this.isRecording = true;
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = () => {
                this.processRecording();
            };
            
            this.mediaRecorder.start();
            this.elements.micButton.classList.add('recording');
            this.showStatus('Recording... Release to translate', 'recording');
            
        } catch (error) {
            this.showError('Failed to start recording. Please check microphone permissions.');
        }
    }
    
    stopRecording() {
        if (!this.isRecording) return;
        
        this.isRecording = false;
        this.mediaRecorder.stop();
        this.elements.micButton.classList.remove('recording');
        this.showStatus('Processing...', 'connected');
        
        // Stop all tracks
        this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    
    async processRecording() {
        if (this.audioChunks.length === 0) return;
        
        try {
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm;codecs=opus' });
            console.log('Recorded audioBlob size:', audioBlob.size);
            // Convert to base64 for transmission
            const arrayBuffer = await audioBlob.arrayBuffer();
            const base64Audio = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
            console.log('Sending audio to server, base64 length:', base64Audio.length);
            // Send audio to server
            this.socket.emit('audio_data', {
                room_id: this.currentRoom,
                audio: base64Audio
            });
            this.showStatus('Audio sent for translation', 'connected');
        } catch (error) {
            this.showError('Failed to process audio recording.');
        }
    }
    
    handleTranslatedAudio(data) {
        console.log('Received translated_audio:', data);
        
        // Check if this translation is intended for this user
        if (data.target_user && data.target_user !== this.socket.id) {
            console.log('Translation not intended for this user, ignoring');
            return;
        }
        
        // Add message to conversation
        this.addMessage('received', data.text, data.original_text);
        // Play translated audio
        this.playAudio(data.audio);
    }
    
    playAudio(base64Audio) {
        try {
            console.log('Playing audio, base64 length:', base64Audio ? base64Audio.length : 0);
            const audioData = atob(base64Audio);
            const audioArray = new Uint8Array(audioData.length);
            for (let i = 0; i < audioData.length; i++) {
                audioArray[i] = audioData.charCodeAt(i);
            }
            const audioBlob = new Blob([audioArray], { type: 'audio/mpeg' });
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audio.onended = () => {
                URL.revokeObjectURL(audioUrl);
            };
            audio.play().catch(error => {
                console.warn('Audio playback failed:', error);
            });
        } catch (error) {
            console.error('Error playing audio:', error);
        }
    }
    
    addMessage(type, text, originalText = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        const headerDiv = document.createElement('div');
        headerDiv.className = 'message-header';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.textContent = text;
        
        if (type === 'system') {
            headerDiv.textContent = 'System';
        } else if (type === 'received') {
            headerDiv.textContent = 'Translated';
            if (originalText) {
                const originalDiv = document.createElement('div');
                originalDiv.style.opacity = '0.7';
                originalDiv.style.fontSize = '0.9em';
                originalDiv.style.marginTop = '0.3rem';
                originalDiv.textContent = `Original: ${originalText}`;
                textDiv.appendChild(originalDiv);
            }
        } else if (type === 'sent') {
            headerDiv.textContent = 'You';
        }
        
        messageDiv.appendChild(headerDiv);
        messageDiv.appendChild(textDiv);
        
        this.elements.conversation.appendChild(messageDiv);
        this.elements.conversation.scrollTop = this.elements.conversation.scrollHeight;
    }
    
    updateUsersList() {
        // This would be enhanced with actual user data from the server
        // For now, just show the count
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
        
        this.isConnected = false;
        this.currentRoom = null;
        this.showSetupSection();
        this.showStatus('Disconnected');
        this.elements.conversation.innerHTML = '';
    }
    
    showStatus(message, type = '') {
        this.elements.status.textContent = message;
        this.elements.status.className = `status ${type}`;
    }
    
    showError(message) {
        this.elements.error.textContent = message;
        this.elements.error.style.display = 'block';
        setTimeout(() => this.hideError(), 5000);
    }
    
    hideError() {
        this.elements.error.style.display = 'none';
    }
    
    showLoading(show) {
        this.elements.loading.style.display = show ? 'block' : 'none';
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new VoiceTranslator();
});