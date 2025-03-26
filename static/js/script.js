document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const discussionForm = document.getElementById('discussionForm');
    const documentUploadForm = document.getElementById('documentUploadForm');
    const topicInput = document.getElementById('topic');
    const numTurnsInput = document.getElementById('numTurns');
    const rolesContainer = document.getElementById('rolesContainer');
    const addRoleBtn = document.getElementById('addRoleBtn');
    const generateBtn = document.getElementById('generateBtn');
    const generateWithDocBtn = document.getElementById('generateWithDocBtn');
    const discussionContainer = document.getElementById('discussionContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const actionItemsLoadingIndicator = document.getElementById('actionItemsLoadingIndicator');
    const errorDisplay = document.getElementById('errorDisplay');
    const errorMessage = document.getElementById('errorMessage');
    const discussionTopicHeader = document.getElementById('discussionTopicHeader');
    const exportTextBtn = document.getElementById('exportText');
    const copyTextBtn = document.getElementById('copyText');
    const generateActionItemsBtn = document.getElementById('generateActionItems');
    const actionItemsContainer = document.getElementById('actionItemsContainer');
    const actionItemsContent = document.getElementById('actionItemsContent');
    const documentUploadStatus = document.getElementById('documentUploadStatus');
    const documentUploadError = document.getElementById('documentUploadError');
    const documentErrorMessage = document.getElementById('documentErrorMessage');
    const uploadedFileName = document.getElementById('uploadedFileName');
    const documentInfo = document.getElementById('documentInfo');
    const documentName = document.getElementById('documentName');
    const clearDocumentBtn = document.getElementById('clearDocument');
    const exampleTopics = document.querySelectorAll('.example-topic');

    // 現在のディスカッションデータ保存用
    let currentDiscussion = null;

    // Initialize the page
    initPage();

    function initPage() {
        // Event listeners
        discussionForm.addEventListener('submit', handleFormSubmit);
        documentUploadForm.addEventListener('submit', handleDocumentUpload);
        addRoleBtn.addEventListener('click', addRoleInput);
        exportTextBtn.addEventListener('click', exportDiscussion);
        copyTextBtn.addEventListener('click', copyDiscussion);
        generateActionItemsBtn.addEventListener('click', generateActionItems);
        generateWithDocBtn.addEventListener('click', handleGenerateWithDocument);
        clearDocumentBtn.addEventListener('click', clearUploadedDocument);
        
        // Example topics
        exampleTopics.forEach(example => {
            example.addEventListener('click', loadExampleTopic);
        });

        // Enable removal buttons if there are more than 2 roles
        updateRemoveButtons();
        
        // Add event listener to role removal buttons
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('remove-role-btn') || 
                e.target.closest('.remove-role-btn')) {
                removeRoleInput(e);
            }
        });
        
        // Check for uploaded document in session
        checkDocumentSession();
    }
    
    function handleFormSubmit(e) {
        e.preventDefault();
        
        // Get values from form
        const topic = topicInput.value.trim();
        const numTurns = parseInt(numTurnsInput.value);
        
        // Get all role inputs
        const roleInputs = document.querySelectorAll('.role-input');
        const roles = Array.from(roleInputs).map(input => input.value.trim()).filter(role => role);
        
        // Validate inputs
        if (!topic) {
            showError('ディスカッションテーマを入力してください');
            return;
        }
        
        if (roles.length < 2) {
            showError('少なくとも2つの役割を追加してください');
            return;
        }
        
        if (numTurns < 1 || numTurns > 10) {
            showError('ターン数は1から10の間で設定してください');
            return;
        }
        
        // Generate discussion
        generateDiscussion(topic, roles, numTurns);
    }
    
    function generateDiscussion(topic, roles, numTurns) {
        // Show loading indicator
        showLoading(true);
        hideError();
        
        // Update header
        discussionTopicHeader.textContent = `ディスカッション: ${topic}`;
        
        // Get selected language
        const language = document.getElementById('language').value;
        
        // Prepare request data
        const requestData = {
            topic: topic,
            roles: roles,
            num_turns: numTurns,
            language: language
        };
        
        // Set timeout for long-running requests
        const timeoutDuration = 60000; // 60 seconds
        let timeoutId;
        
        const timeoutPromise = new Promise((_, reject) => {
            timeoutId = setTimeout(() => {
                reject(new Error('ディスカッション生成がタイムアウトしました。サーバーが混雑しているか、複雑なリクエストの可能性があります。'));
            }, timeoutDuration);
        });
        
        // Fetch API request
        const fetchPromise = fetch('/generate-discussion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        // Race between fetch and timeout
        Promise.race([fetchPromise, timeoutPromise])
            .then(response => {
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json().then(errorData => {
                            throw new Error(errorData.error || `サーバーエラー: ${response.status}`);
                        });
                    } else {
                        return response.text().then(errorText => {
                            if (errorText.includes('<html>')) {
                                throw new Error(`サーバー内部エラー: ディスカッション生成中にエラーが発生しました。`);
                            } else {
                                throw new Error(`サーバーエラー: ${response.status} - ${errorText.slice(0, 100)}`);
                            }
                        });
                    }
                }
                
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return response.json();
                } else {
                    throw new Error('サーバーから無効なレスポンスフォーマットが返されました');
                }
            })
            .then(data => {
                showLoading(false);
                
                if (data.error) {
                    showError(data.error);
                    return;
                }
                
                // Store current discussion
                currentDiscussion = data.discussion;
                
                displayDiscussion(data.discussion, topic);
                enableExportButtons();
            })
            .catch(error => {
                clearTimeout(timeoutId);
                showLoading(false);
                
                let errorMsg = error.message || 'ディスカッションの生成中にエラーが発生しました';
                showError(errorMsg);
                console.error('Error generating discussion:', error);
            });
    }
    
    function displayDiscussion(discussion, topic) {
        discussionContainer.innerHTML = '';
        
        discussion.forEach((msg, index) => {
            const isEven = index % 2 === 0;
            const bubble = document.createElement('div');
            bubble.className = `discussion-bubble ${isEven ? 'left' : 'right'} mb-3`;
            
            bubble.innerHTML = `
                <div class="role-tag">${msg.role}</div>
                <div class="message-content">${msg.content}</div>
            `;
            
            discussionContainer.appendChild(bubble);
        });
        
        // Enable action items button
        generateActionItemsBtn.disabled = false;
    }
    
    function addRoleInput() {
        const roleInputs = document.querySelectorAll('.role-input');
        
        if (roleInputs.length >= 6) {
            showError('最大6つまでの役割を設定できます');
            return;
        }
        
        const div = document.createElement('div');
        div.className = 'input-group mb-2';
        div.innerHTML = `
            <input type="text" class="form-control role-input" placeholder="役割の説明" required>
            <button class="btn btn-outline-danger remove-role-btn" type="button">
                <i class="bi bi-trash"></i>
            </button>
        `;
        
        rolesContainer.appendChild(div);
        updateRemoveButtons();
    }
    
    function removeRoleInput(e) {
        const button = e.target.closest('.remove-role-btn');
        if (!button) return;
        
        button.closest('.input-group').remove();
        updateRemoveButtons();
    }
    
    function updateRemoveButtons() {
        const roleInputs = document.querySelectorAll('.role-input');
        const removeButtons = document.querySelectorAll('.remove-role-btn');
        
        // Disable remove buttons if there are only 2 roles
        removeButtons.forEach(button => {
            button.disabled = roleInputs.length <= 2;
        });
    }
    
    function loadExampleTopic(e) {
        const topic = e.target.getAttribute('data-topic');
        const roles = JSON.parse(e.target.getAttribute('data-roles'));
        
        // Set topic
        topicInput.value = topic;
        
        // Clear existing roles
        rolesContainer.innerHTML = '';
        
        // Add roles
        roles.forEach(role => {
            const div = document.createElement('div');
            div.className = 'input-group mb-2';
            div.innerHTML = `
                <input type="text" class="form-control role-input" placeholder="役割の説明" value="${role}" required>
                <button class="btn btn-outline-danger remove-role-btn" type="button">
                    <i class="bi bi-trash"></i>
                </button>
            `;
            
            rolesContainer.appendChild(div);
        });
        
        updateRemoveButtons();
    }
    
    function showLoading(isLoading) {
        if (isLoading) {
            loadingIndicator.classList.remove('d-none');
            discussionContainer.classList.add('d-none');
            generateBtn.disabled = true;
            generateWithDocBtn.disabled = true;
            generateActionItemsBtn.disabled = true;
        } else {
            loadingIndicator.classList.add('d-none');
            discussionContainer.classList.remove('d-none');
            generateBtn.disabled = false;
            generateWithDocBtn.disabled = document.getElementById('documentInfo').classList.contains('d-none');
            generateActionItemsBtn.disabled = discussionContainer.children.length === 0;
        }
    }
    
    function showActionItemsLoading(isLoading) {
        if (isLoading) {
            actionItemsLoadingIndicator.classList.remove('d-none');
            generateActionItemsBtn.disabled = true;
        } else {
            actionItemsLoadingIndicator.classList.add('d-none');
            generateActionItemsBtn.disabled = false;
        }
    }
    
    function showError(message) {
        errorMessage.textContent = message;
        errorDisplay.classList.remove('d-none');
    }
    
    function hideError() {
        errorDisplay.classList.add('d-none');
    }
    
    function enableExportButtons() {
        exportTextBtn.disabled = false;
        copyTextBtn.disabled = false;
    }
    
    function exportDiscussion() {
        const text = getDiscussionText();
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `discussion_${new Date().toISOString().slice(0, 10)}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    function copyDiscussion() {
        const text = getDiscussionText();
        
        navigator.clipboard.writeText(text)
            .then(() => {
                const originalText = copyTextBtn.innerHTML;
                copyTextBtn.innerHTML = '<i class="bi bi-check"></i> コピー完了';
                
                setTimeout(() => {
                    copyTextBtn.innerHTML = originalText;
                }, 2000);
            })
            .catch(err => {
                console.error('クリップボードへのコピーに失敗しました:', err);
                showError('クリップボードへのコピーに失敗しました');
            });
    }
    
    function getDiscussionText() {
        let text = `ディスカッション: ${discussionTopicHeader.textContent}\n\n`;
        
        const bubbles = discussionContainer.querySelectorAll('.discussion-bubble');
        bubbles.forEach(bubble => {
            const role = bubble.querySelector('.role-tag').textContent;
            const content = bubble.querySelector('.message-content').textContent;
            
            text += `【${role}】\n${content}\n\n`;
        });
        
        return text;
    }
    
    function handleDocumentUpload(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('documentFile');
        const file = fileInput.files[0];
        
        if (!file) {
            showDocumentError('ファイルが選択されていません。');
            return;
        }
        
        // ファイルサイズチェック (5MB)
        if (file.size > 5 * 1024 * 1024) {
            showDocumentError('ファイルサイズが大きすぎます。5MB以下のファイルを選択してください。');
            return;
        }
        
        // 拡張子チェック
        const fileExt = file.name.split('.').pop().toLowerCase();
        if (!['pdf', 'txt', 'docx'].includes(fileExt)) {
            showDocumentError('サポートされていないファイル形式です。PDF, TXT, DOCXのいずれかを選択してください。');
            return;
        }
        
        // FormDataの作成
        const formData = new FormData();
        formData.append('file', file);
        
        // エラー表示をクリア
        hideDocumentError();
        
        // アップロードボタンの状態を変更
        const uploadBtn = document.getElementById('uploadDocumentBtn');
        const originalText = uploadBtn.innerHTML;
        uploadBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> アップロード中...';
        uploadBtn.disabled = true;
        
        // ファイルアップロード
        fetch('/upload-document', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || `サーバーエラー: ${response.status}`);
                    });
                } else {
                    return response.text().then(errorText => {
                        if (errorText.includes('<html>')) {
                            throw new Error(`サーバー内部エラー: ファイルアップロード中にエラーが発生しました。`);
                        } else {
                            throw new Error(`サーバーエラー: ${response.status} - ${errorText.slice(0, 100)}`);
                        }
                    });
                }
            }
            return response.json();
        })
        .then(data => {
            // アップロード成功の表示
            uploadBtn.innerHTML = originalText;
            uploadBtn.disabled = false;
            
            if (data.success) {
                // セッションに保存
                sessionStorage.setItem('uploadedDocument', JSON.stringify({
                    name: file.name,
                    type: file.type
                }));
                
                showDocumentSuccess(file.name);
                updateDocumentInfo(file.name);
                
                // ドキュメントを使用したディスカッション生成を有効化
                generateWithDocBtn.disabled = false;
            } else {
                showDocumentError(data.error || 'ドキュメントの処理に失敗しました。');
            }
        })
        .catch(error => {
            uploadBtn.innerHTML = originalText;
            uploadBtn.disabled = false;
            showDocumentError(error.message);
            console.error('Error uploading document:', error);
        });
    }
    
    function showDocumentSuccess(fileName) {
        uploadedFileName.textContent = fileName;
        documentUploadStatus.classList.remove('d-none');
    }
    
    function hideDocumentSuccess() {
        documentUploadStatus.classList.add('d-none');
    }
    
    function showDocumentError(message) {
        documentErrorMessage.textContent = message;
        documentUploadError.classList.remove('d-none');
    }
    
    function hideDocumentError() {
        documentUploadError.classList.add('d-none');
    }
    
    function updateDocumentInfo(fileName) {
        documentName.textContent = fileName;
        documentInfo.classList.remove('d-none');
    }
    
    function clearUploadedDocument() {
        // セッションからドキュメント情報をクリア
        sessionStorage.removeItem('uploadedDocument');
        
        // サーバーセッションもクリア
        fetch('/clear-document', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(() => {
            // UI表示をクリア
            documentInfo.classList.add('d-none');
            hideDocumentSuccess();
            
            // ドキュメントを使用したディスカッション生成を無効化
            generateWithDocBtn.disabled = true;
        })
        .catch(error => {
            console.error('Error clearing document:', error);
        });
    }
    
    function checkDocumentSession() {
        // セッションストレージからドキュメント情報を取得
        const documentData = sessionStorage.getItem('uploadedDocument');
        
        if (documentData) {
            try {
                const { name } = JSON.parse(documentData);
                updateDocumentInfo(name);
                generateWithDocBtn.disabled = false;
            } catch (e) {
                console.error('Error parsing document data:', e);
                sessionStorage.removeItem('uploadedDocument');
            }
        }
    }
    
    function handleGenerateWithDocument() {
        // Get values from form
        const topic = topicInput.value.trim();
        const numTurns = parseInt(numTurnsInput.value);
        
        // Get all role inputs
        const roleInputs = document.querySelectorAll('.role-input');
        const roles = Array.from(roleInputs).map(input => input.value.trim()).filter(role => role);
        
        // Validate inputs
        if (!topic) {
            showError('ディスカッションテーマを入力してください');
            return;
        }
        
        if (roles.length < 2) {
            showError('少なくとも2つの役割を追加してください');
            return;
        }
        
        if (numTurns < 1 || numTurns > 10) {
            showError('ターン数は1から10の間で設定してください');
            return;
        }
        
        // セッションにドキュメントがあるか確認
        if (!sessionStorage.getItem('uploadedDocument')) {
            showError('有効なドキュメントがアップロードされていません。先にドキュメントをアップロードしてください。');
            return;
        }
        
        // 生成処理の開始
        generateDiscussionWithDocument(topic, roles, numTurns);
    }
    
    function generateDiscussionWithDocument(topic, roles, numTurns) {
        // Show loading indicator
        showLoading(true);
        hideError();
        
        // Update header
        discussionTopicHeader.textContent = `ディスカッション: ${topic} (文書参照)`;
        
        // Get selected language
        const language = document.getElementById('language').value;
        
        // Prepare request data
        const requestData = {
            topic: topic,
            roles: roles,
            num_turns: numTurns,
            language: language
        };
        
        // Set timeout for long-running requests
        const timeoutDuration = 90000; // 90 seconds (longer for document-based discussions)
        let timeoutId;
        
        const timeoutPromise = new Promise((_, reject) => {
            timeoutId = setTimeout(() => {
                reject(new Error('ディスカッション生成がタイムアウトしました。サーバーが混雑しているか、複雑なリクエストの可能性があります。'));
            }, timeoutDuration);
        });
        
        // Fetch API request
        const fetchPromise = fetch('/generate-discussion-with-document', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        // Race between fetch and timeout
        Promise.race([fetchPromise, timeoutPromise])
            .then(response => {
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json().then(errorData => {
                            throw new Error(errorData.error || `サーバーエラー: ${response.status}`);
                        });
                    } else {
                        return response.text().then(errorText => {
                            if (errorText.includes('<html>')) {
                                throw new Error(`サーバー内部エラー: ディスカッション生成中にエラーが発生しました。`);
                            } else {
                                throw new Error(`サーバーエラー: ${response.status} - ${errorText.slice(0, 100)}`);
                            }
                        });
                    }
                }
                
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return response.json();
                } else {
                    throw new Error('サーバーから無効なレスポンスフォーマットが返されました');
                }
            })
            .then(data => {
                showLoading(false);
                
                if (data.error) {
                    showError(data.error);
                    return;
                }
                
                // Store current discussion
                currentDiscussion = data.discussion;
                
                displayDiscussion(data.discussion, topic);
                enableExportButtons();
            })
            .catch(error => {
                clearTimeout(timeoutId);
                showLoading(false);
                
                let errorMsg = error.message || 'ディスカッションの生成中にエラーが発生しました';
                showError(errorMsg);
                console.error('Error generating discussion with document:', error);
            });
    }
    
    // アクションアイテム生成機能
    function generateActionItems() {
        // ディスカッションデータがあることを確認
        const bubbles = discussionContainer.querySelectorAll('.discussion-bubble');
        if (bubbles.length === 0) {
            showError('アクションアイテムを生成するためのディスカッションデータがありません。');
            return;
        }
        
        // ディスカッションデータを収集
        const discussionData = [];
        bubbles.forEach(bubble => {
            const role = bubble.querySelector('.role-tag').textContent;
            const content = bubble.querySelector('.message-content').textContent;
            
            discussionData.push({
                role: role,
                content: content
            });
        });
        
        // Get selected language
        const language = document.getElementById('language').value;
        
        // ローディング表示
        showActionItemsLoading(true);
        hideError();
        
        // アクションアイテムコンテナを表示
        actionItemsContainer.classList.remove('d-none');
        actionItemsContent.innerHTML = '<div class="text-center"><p>アクションアイテムを生成中...</p></div>';
        
        // タイムアウト処理
        const timeoutDuration = 60000; // 60秒
        let timeoutId;
        
        const timeoutPromise = new Promise((_, reject) => {
            timeoutId = setTimeout(() => {
                reject(new Error('アクションアイテム生成がタイムアウトしました。'));
            }, timeoutDuration);
        });
        
        // リクエスト送信
        const fetchPromise = fetch('/generate-action-items', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                discussion_data: discussionData,
                language: language
            })
        });
        
        // リクエストとタイムアウトを競合
        Promise.race([fetchPromise, timeoutPromise])
            .then(response => {
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json().then(errorData => {
                            throw new Error(errorData.error || `サーバーエラー: ${response.status}`);
                        });
                    } else {
                        return response.text().then(errorText => {
                            if (errorText.includes('<html>')) {
                                throw new Error(`サーバー内部エラー: アクションアイテム生成中にエラーが発生しました。`);
                            } else {
                                throw new Error(`サーバーエラー: ${response.status} - ${errorText.slice(0, 100)}`);
                            }
                        });
                    }
                }
                
                return response.json();
            })
            .then(data => {
                showActionItemsLoading(false);
                
                if (data.error) {
                    showError(data.error);
                    actionItemsContainer.classList.add('d-none');
                    return;
                }
                
                // MarkdownをHTMLに変換
                actionItemsContent.innerHTML = markdownToHtml(data.markdown_content);
                
                // スクロールして表示
                actionItemsContainer.scrollIntoView({ behavior: 'smooth' });
            })
            .catch(error => {
                clearTimeout(timeoutId);
                showActionItemsLoading(false);
                actionItemsContainer.classList.add('d-none');
                
                let errorMsg = error.message || 'アクションアイテムの生成中にエラーが発生しました';
                showError(errorMsg);
                console.error('Error generating action items:', error);
            });
    }
    
    // Markdown を HTML に変換する簡易関数
    function markdownToHtml(markdown) {
        if (!markdown) return '';
        
        // 安全のためにHTMLエスケープ
        let html = escapeHtml(markdown);
        
        // 見出し
        html = html.replace(/^### (.*$)/gim, '<h5>$1</h5>');
        html = html.replace(/^## (.*$)/gim, '<h4>$1</h4>');
        html = html.replace(/^# (.*$)/gim, '<h3>$1</h3>');
        
        // 太字
        html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
        
        // リスト
        html = html.replace(/^\d+\. (.*$)/gim, '<li>$1</li>');
        html = html.replace(/<\/li>\n<li>/gim, '</li><li>');
        html = html.replace(/(<li>.*<\/li>)/gim, '<ol>$1</ol>');
        
        // 改行
        html = html.replace(/\n/gim, '<br>');
        
        return html;
    }
    
    // HTML特殊文字をエスケープする関数
    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
});