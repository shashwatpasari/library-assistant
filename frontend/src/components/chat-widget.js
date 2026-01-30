/**
 * Shared chat widget component for all pages
 * Provides consistent AI assistant chat interface with minimize/expand functionality
 */

/**
 * Renders the chat widget HTML
 * @param {Object} options - Configuration options
 * @param {string} options.greeting - Custom greeting message
 * @param {string} options.bookTitle - Book title for context (optional)
 * @param {Array<string>} options.suggestedQuestions - Array of suggested questions (optional)
 * @returns {string} HTML string for the chat widget
 */
export function renderChatWidget(options = {}) {
    const {
        greeting = "Hello! I'm your AI assistant. How can I help you today?",
        bookTitle = null,
        suggestedQuestions = []
    } = options;

    const greetingText = bookTitle
        ? `Hello! I'm your AI assistant. Ask me anything about "${bookTitle}".`
        : greeting;

    const suggestedQuestionsHTML = suggestedQuestions.length > 0
        ? `
            <div class="flex flex-col gap-2 mt-4">
                <p class="text-xs text-[#637588] dark:text-gray-400 mb-1">Suggested questions:</p>
                ${suggestedQuestions.map(q => `
                    <button class="suggested-question text-left px-3 py-2 bg-primary/10 dark:bg-primary/20 text-primary dark:text-primary-300 rounded-lg text-sm hover:bg-primary/20 dark:hover:bg-primary/30 transition-colors">
                        ${escapeHtml(q)}
                    </button>
                `).join('')}
            </div>
        `
        : '';

    const styles = `
        <style>
            .book-card-grid {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                margin: 12px 0;
            }
            .book-card-item {
                width: 120px;
                background: #1e1e2e;
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid #2a2a3e;
                position: relative;
                transition: transform 0.2s;
            }
            .book-card-item:hover {
                transform: translateY(-2px);
                border-color: #3b3b55;
            }
            .book-card-image-container {
                position: relative;
                height: 160px;
                width: 100%;
            }
            .book-card-image {
                width: 100%;
                height: 100%;
                object-fit: cover;
                display: block;
            }
            .book-card-placeholder {
                width: 100%;
                height: 100%;
                background: #2a2a3e;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #555;
                font-size: 10px;
            }
            .book-like-btn {
                position: absolute;
                top: 8px;
                right: 8px;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                background: rgba(255,255,255,0.8);
                backdrop-filter: blur(4px);
                border: none;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.2s;
                color: #475569;
                z-index: 10;
            }
            .book-like-btn:hover {
                background: white;
                color: #ef4444;
                transform: scale(1.1);
            }
            .book-card-details {
                padding: 10px;
                display: block;
                text-decoration: none;
            }
            .book-card-title {
                font-weight: 600;
                font-size: 12px;
                color: #fff;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .book-card-author {
                font-size: 10px;
                color: #94a3b8;
                margin-top: 2px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
        </style>
    `;

    return styles + `
        <div class="fixed bottom-4 right-4 z-40">
            <!-- Collapsed state: Just a button -->
            <button id="chat-toggle" class="w-14 h-14 rounded-full bg-primary text-white shadow-lg hover:bg-primary/90 transition-all flex items-center justify-center">
                <span class="material-symbols-outlined !text-2xl">chat</span>
            </button>
            <!-- Expanded state: Full chat widget - 50vw/90vh -->
            <div id="chat-widget" class="hidden w-[50vw] h-[90vh] bg-white dark:bg-gray-900/95 backdrop-blur-sm rounded-xl border border-gray-200 dark:border-gray-800 shadow-xl flex flex-col">
                <div class="p-4 border-b border-gray-200 dark:border-gray-800 flex-shrink-0 flex items-center justify-between">
                    <div>
                        <h3 class="font-bold text-lg text-[#111418] dark:text-white">Ask an Assistant</h3>
                        <p class="text-sm text-[#637588] dark:text-gray-400">Powered by RAG AI</p>
                    </div>
                    <button id="chat-close" class="flex items-center justify-center w-8 h-8 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors" title="Minimize chat">
                        <span class="material-symbols-outlined !text-xl text-[#637588] dark:text-gray-400">expand_more</span>
                    </button>
                </div>
                <div id="chat-messages" class="flex-1 p-4 overflow-y-auto space-y-4">
                    <div class="flex justify-start">
                        <div class="bg-gray-100 dark:bg-gray-800 p-3 rounded-lg max-w-xs">
                            <p class="text-sm text-[#111418] dark:text-gray-200">${escapeHtml(greetingText)}</p>
                        </div>
                    </div>
                    ${suggestedQuestionsHTML}
                </div>
                <div class="p-4 border-t border-gray-200 dark:border-gray-800 flex-shrink-0 bg-white dark:bg-gray-900/80 rounded-b-xl">
                    <div class="flex items-center gap-2">
                        <input id="chat-input" class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-[#111418] dark:text-gray-200 focus:outline-0 focus:ring-2 focus:ring-primary border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 focus:border-primary h-11 placeholder:text-[#637588] dark:placeholder:text-gray-500 px-4 text-sm font-normal leading-normal" placeholder="Ask a question..."/>
                        <button id="chat-mic" class="flex shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-lg h-11 w-11 bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors" title="Voice input">
                            <span class="material-symbols-outlined !text-xl">mic</span>
                        </button>
                        <button id="chat-send" class="flex shrink-0 max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-11 w-11 bg-primary text-white hover:bg-primary/90 transition-colors">
                            <span class="material-symbols-outlined !text-xl">send</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Initializes chat widget functionality
 */
export function initChatWidget() {
    const chatToggle = document.getElementById('chat-toggle');
    const chatWidget = document.getElementById('chat-widget');
    const chatClose = document.getElementById('chat-close');
    const chatSend = document.getElementById('chat-send');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');

    // Conversation history for multi-turn support
    let conversationHistory = [];

    // Global function to save book from chat card like button
    window.saveBookFromChat = async function (bookId) {
        try {
            const token = localStorage.getItem('auth_token');
            if (!token) {
                alert('Please log in to save books');
                return;
            }
            const response = await fetch('http://localhost:8000/saved-books/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ book_id: bookId })
            });
            if (response.ok) {
                alert('Book saved to your collection!');
            } else if (response.status === 400) {
                alert('Book already saved!');
            }
        } catch (error) {
            console.error('Error saving book:', error);
        }
    };

    // Toggle chat widget (expand)
    chatToggle?.addEventListener('click', () => {
        chatToggle.classList.add('hidden');
        chatWidget?.classList.remove('hidden');
        chatInput?.focus();
    });

    // Minimize chat widget (collapse)
    chatClose?.addEventListener('click', () => {
        chatWidget?.classList.add('hidden');
        chatToggle?.classList.remove('hidden');
    });

    // Suggested question buttons
    document.querySelectorAll('.suggested-question').forEach(btn => {
        btn.addEventListener('click', () => {
            const question = btn.textContent.trim();
            sendMessage(question);
        });
    });

    // Send message on button click
    chatSend?.addEventListener('click', () => {
        handleSendMessage();
    });

    // Send message on Enter key
    chatInput?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSendMessage();
        }
    });

    // Voice recording setup
    const chatMic = document.getElementById('chat-mic');
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    chatMic?.addEventListener('click', async () => {
        if (isRecording) {
            // Stop recording
            mediaRecorder?.stop();
        } else {
            // Start recording
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                audioChunks = [];

                mediaRecorder.ondataavailable = (e) => {
                    audioChunks.push(e.data);
                };

                mediaRecorder.onstop = async () => {
                    // Update UI
                    isRecording = false;
                    chatMic.classList.remove('bg-red-500', 'text-white');
                    chatMic.classList.add('bg-gray-200', 'dark:bg-gray-700', 'text-gray-600', 'dark:text-gray-300');
                    chatMic.querySelector('span').textContent = 'mic';

                    // Stop all tracks
                    stream.getTracks().forEach(track => track.stop());

                    // Send audio to transcription API
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    await transcribeAudio(audioBlob);
                };

                mediaRecorder.start();
                isRecording = true;

                // Update UI to show recording
                chatMic.classList.remove('bg-gray-200', 'dark:bg-gray-700', 'text-gray-600', 'dark:text-gray-300');
                chatMic.classList.add('bg-red-500', 'text-white');
                chatMic.querySelector('span').textContent = 'stop';

            } catch (err) {
                console.error('Microphone access denied:', err);
                alert('Please allow microphone access to use voice input.');
            }
        }
    });

    /**
     * Transcribe audio blob using backend Whisper API
     */
    async function transcribeAudio(audioBlob) {
        chatInput.placeholder = 'Transcribing...';
        chatInput.disabled = true;

        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');

            const response = await fetch('http://localhost:8000/voice/transcribe', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                chatInput.value = data.text || '';
                chatInput.focus();
            } else {
                console.error('Transcription failed:', response.status);
            }
        } catch (error) {
            console.error('Transcription error:', error);
        } finally {
            chatInput.placeholder = 'Ask a question...';
            chatInput.disabled = false;
        }
    }

    /**
     * Handles sending a message
     */
    function handleSendMessage() {
        if (!chatInput || !chatMessages) return;

        const question = chatInput.value.trim();
        if (!question) return;

        sendMessage(question);
        chatInput.value = '';
    }

    /**
     * Sends a message and displays the AI response using streaming
     * @param {string} message - The message to send
     */
    async function sendMessage(message) {
        if (!chatMessages) return;

        // Remove suggested questions after first message
        const suggestedContainer = chatMessages.querySelector('.suggested-question')?.parentElement;
        if (suggestedContainer) {
            suggestedContainer.remove();
        }

        // Add user message to history
        conversationHistory.push({ role: "user", content: message });

        // Add user message to UI
        chatMessages.innerHTML += `
            <div class="flex justify-end">
                <div class="bg-primary text-white p-3 rounded-lg max-w-xs">
                    <p class="text-sm">${escapeHtml(message)}</p>
                </div>
            </div>
        `;
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Add loading indicator
        const loadingId = 'loading-' + Date.now();
        chatMessages.innerHTML += `
            <div id="${loadingId}" class="flex justify-start">
                <div class="bg-gray-100 dark:bg-gray-800 p-3 rounded-lg max-w-xs">
                    <p class="text-sm text-[#111418] dark:text-gray-200 flex items-center gap-2">
                        <span class="animate-pulse">●</span>
                        <span class="animate-pulse" style="animation-delay: 0.2s">●</span>
                        <span class="animate-pulse" style="animation-delay: 0.4s">●</span>
                    </p>
                </div>
            </div>
        `;
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch('http://localhost:8000/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify({ messages: conversationHistory })
            });

            // Remove loading indicator
            document.getElementById(loadingId)?.remove();

            if (!response.ok) {
                throw new Error('Failed to get response');
            }

            // Create AI message container for streaming
            const aiMessageId = 'ai-msg-' + Date.now();
            chatMessages.innerHTML += `
                <div class="flex justify-start">
                    <div class="bg-gray-100 dark:bg-gray-800 p-3 rounded-lg max-w-[90%]">
                        <div id="${aiMessageId}" class="text-sm text-[#111418] dark:text-gray-200"></div>
                    </div>
                </div>
            `;

            const aiMessage = document.getElementById(aiMessageId);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullResponse = '';

            // Stream plain text only - no rendering during stream
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                fullResponse += chunk;

                // Show ONLY clean plain text during streaming
                // Strip all special formats completely
                const plainText = fullResponse
                    .replace(/\d*\.?\s*BOOK\[[^\]]+\]/gi, '')  // Remove BOOK[...] completely
                    .replace(/\[SAVE_BOOK:\d+\]/gi, '')        // Remove save actions
                    .trim();
                aiMessage.textContent = plainText;
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }

            // ONLY AFTER streaming is complete: render full formatted response
            // Split response into text and JSON data
            const parts = fullResponse.split('__JSON_START__');
            const textPart = parts[0];
            const jsonPart = parts[1] ? JSON.parse(parts[1]) : null;

            const { formattedResponse, bookIdToSave } = processResponseActions(textPart);
            aiMessage.innerHTML = formatResponseWithImages(formattedResponse, jsonPart);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // Handle save book action if detected
            if (bookIdToSave) {
                await handleSaveBook(bookIdToSave);
            }

            // Add assistant response to history (without action tags)
            conversationHistory.push({ role: "assistant", content: formattedResponse });

        } catch (error) {
            console.error('Chat error:', error);
            document.getElementById(loadingId)?.remove();

            chatMessages.innerHTML += `
                <div class="flex justify-start">
                    <div class="bg-red-100 dark:bg-red-900/30 p-3 rounded-lg max-w-xs">
                        <p class="text-sm text-red-600 dark:text-red-400">Sorry, I couldn't process your request. Please try again.</p>
                    </div>
                </div>
            `;
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    /**
     * Process response for action tags (e.g., SAVE_BOOK:123)
     * @param {string} response - Raw response from AI
     * @returns {Object} { formattedResponse, bookIdToSave }
     */
    function processResponseActions(response) {
        let formattedResponse = response;
        let bookIdToSave = null;

        // Look for SAVE_BOOK action tag
        const saveMatch = response.match(/\[SAVE_BOOK:(\d+)\]/);
        if (saveMatch) {
            bookIdToSave = parseInt(saveMatch[1], 10);
            // Remove the action tag from displayed response
            formattedResponse = response.replace(/\[SAVE_BOOK:\d+\]/g, '').trim();
        }

        return { formattedResponse, bookIdToSave };
    }

    /**
     * Handles saving a book via API
     * @param {number} bookId - ID of book to save
     */
    async function handleSaveBook(bookId) {
        const token = localStorage.getItem('token');
        if (!token) {
            // Not logged in - show message to user
            chatMessages.innerHTML += `
                <div class="flex justify-start">
                    <div class="bg-yellow-100 dark:bg-yellow-900/30 p-3 rounded-lg max-w-xs">
                        <p class="text-sm text-yellow-700 dark:text-yellow-400">Please log in to save books to your collection.</p>
                    </div>
                </div>
            `;
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return;
        }

        try {
            const response = await fetch(`http://localhost:8000/saved-books/${bookId}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                chatMessages.innerHTML += `
                    <div class="flex justify-start">
                        <div class="bg-green-100 dark:bg-green-900/30 p-3 rounded-lg max-w-xs">
                            <p class="text-sm text-green-700 dark:text-green-400">✓ Book saved to your collection!</p>
                        </div>
                    </div>
                `;
            } else {
                console.error('Failed to save book:', response.status);
            }
        } catch (error) {
            console.error('Error saving book:', error);
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

/**
 * Formats response text with book cards and markdown rendering
 * @param {string} text - Response text to format
 * @param {Array} bookData - Optional array of book objects to render cards
 * @returns {string} HTML formatted text with book cards
 */
function formatResponseWithImages(text, bookData = null) {
    if (!text) return '';

    // Clean text of technical tags if any leak through
    let cleanText = text.replace(/BID\[\d+\]/g, '');

    // Clean up numbered lists remnants
    cleanText = cleanText.replace(/^\s*\d+\.\s*$/gm, '');
    cleanText = cleanText.replace(/^\s*-\s*$/gm, '');

    // Escape the clean text
    let finalHtml = escapeHtml(cleanText);

    // Convert markdown (bold, etc)
    finalHtml = finalHtml
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/###\s+(.+)$/gm, '<h3 class="text-sm font-bold mt-2">$1</h3>')
        .replace(/\n/g, '<br>'); // Convert newlines to breaks for list formatting

    // Generate Book Cards if data is provided
    if (bookData && bookData.length > 0) {
        let gridHtml = '<div class="book-card-grid">';
        bookData.forEach(book => {
            const coverHtml = book.cover
                ? `<img src="${book.cover}" alt="${book.title}" class="book-card-image" onerror="this.onerror=null;this.src='https://via.placeholder.com/120x160?text=No+Cover'">`
                : '<div class="book-card-placeholder">No Cover</div>';

            gridHtml += `
            <div class="book-card-item">
                <div class="book-card-image-container">
                    <a href="book.html?id=${book.id}" target="_blank">
                        ${coverHtml}
                    </a>
                    <button class="book-like-btn" onclick="event.preventDefault(); window.saveBookFromChat('${book.id}')" title="Save to my books">
                        <span class="material-symbols-outlined" style="font-size:20px;">favorite</span>
                    </button>
                </div>
                <a href="book.html?id=${book.id}" target="_blank" class="book-card-details">
                    <div class="book-card-title">${book.title}</div>
                    <div class="book-card-author">${book.author}</div>
                </a>
            </div>`;
        });
        gridHtml += '</div>';
        finalHtml += gridHtml;
    }

    return finalHtml;
}

/**
 * Escapes HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

