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
        
        // Check for session storage
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
            showError('Please enter a discussion topic');
            return;
        }
        
        if (roles.length < 2) {
            showError('Please add at least two roles');
            return;
        }
        
        if (numTurns < 1 || numTurns > 10) {
            showError('Number of turns must be between 1 and 10');
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
        
        // タイムアウト処理を追加
        const timeoutDuration = 120000; // 120秒
        let timeoutId;
        
        const timeoutPromise = new Promise((_, reject) => {
            timeoutId = setTimeout(() => {
                reject(new Error('リクエストがタイムアウトしました。少ないロール数やターン数で再試行してください。'));
            }, timeoutDuration);
        });
        
        // リクエスト送信
        const fetchPromise = fetch('/generate-discussion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        // リクエストとタイムアウトを競合
        Promise.race([fetchPromise, timeoutPromise])
            .then(response => {
                clearTimeout(timeoutId);
                
                // レスポンスのステータスコードをチェック
                if (!response.ok) {
                    // レスポンスのContent-Typeをチェック
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json().then(errorData => {
                            throw new Error(errorData.error || `サーバーエラー: ${response.status}`);
                        });
                    } else {
                        // JSONでない場合はテキストとして扱う
                        return response.text().then(errorText => {
                            // HTMLレスポンスの場合は一般的なエラーメッセージを表示
                            if (errorText.includes('<html>')) {
                                throw new Error(`サーバー内部エラー: リソース制限に達しました。少ないターン数でお試しください。`);
                            } else {
                                throw new Error(`サーバーエラー: ${response.status} - ${errorText.slice(0, 100)}`);
                            }
                        });
                    }
                }
                
                // 正常なレスポンスの場合はJSONとして解析
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
                
                displayDiscussion(data.discussion, topic);
                enableExportButtons();
            })
            .catch(error => {
                clearTimeout(timeoutId);
                showLoading(false);
                
                // エラーメッセージを表示
                let errorMsg = error.message || 'ディスカッションの生成中にエラーが発生しました';
                showError(errorMsg);
                console.error('Error generating discussion:', error);
            });
    }
    
    function displayDiscussion(discussion, topic) {
        // Clear discussion container
        discussionContainer.innerHTML = '';
        
        // Add topic header
        const topicHeader = document.createElement('h4');
        topicHeader.textContent = `Topic: ${topic}`;
        topicHeader.className = 'mb-4';
        discussionContainer.appendChild(topicHeader);
        
        // Group messages by roles
        const groupedByRole = {};
        discussion.forEach(item => {
            if (!groupedByRole[item.role]) {
                groupedByRole[item.role] = [];
            }
            groupedByRole[item.role].push(item.content);
        });
        
        // Display each message
        discussion.forEach((item, index) => {
            const messageElement = document.createElement('div');
            messageElement.className = 'discussion-bubble';
            
            // Determine which side to place the message
            const roleIndex = Object.keys(groupedByRole).indexOf(item.role);
            messageElement.className += roleIndex % 2 === 0 ? ' left' : ' right';
            
            // Create role label
            const roleLabel = document.createElement('div');
            roleLabel.className = 'role-tag';
            roleLabel.textContent = item.role;
            
            // Create message content
            const content = document.createElement('div');
            content.className = 'message-content';
            content.textContent = item.content;
            
            // Assemble message
            messageElement.appendChild(roleLabel);
            messageElement.appendChild(content);
            
            // Add to container
            discussionContainer.appendChild(messageElement);
        });
        
        // Scroll to the bottom
        discussionContainer.scrollTop = discussionContainer.scrollHeight;
    }
    
    function addRoleInput() {
        const roleCount = document.querySelectorAll('.role-input').length;
        
        // Create new role input
        const inputGroup = document.createElement('div');
        inputGroup.className = 'input-group mb-2';
        
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control role-input';
        input.placeholder = 'Role description';
        input.required = true;
        
        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn btn-outline-danger remove-role-btn';
        removeBtn.type = 'button';
        removeBtn.innerHTML = '<i class="bi bi-trash"></i>';
        removeBtn.addEventListener('click', removeRoleInput);
        
        inputGroup.appendChild(input);
        inputGroup.appendChild(removeBtn);
        rolesContainer.appendChild(inputGroup);
        
        // Update remove buttons
        updateRemoveButtons();
        
        // Focus on the new input
        input.focus();
    }
    
    function removeRoleInput(e) {
        const inputGroup = e.target.closest('.input-group');
        inputGroup.remove();
        
        // Update remove buttons
        updateRemoveButtons();
    }
    
    function updateRemoveButtons() {
        const removeButtons = document.querySelectorAll('.remove-role-btn');
        const roleCount = document.querySelectorAll('.role-input').length;
        
        // Enable remove buttons only if there are more than 2 roles
        removeButtons.forEach(button => {
            button.disabled = roleCount <= 2;
        });
    }
    
    function loadExampleTopic(e) {
        const example = e.target;
        const topic = example.dataset.topic;
        const roles = JSON.parse(example.dataset.roles);
        
        // Set topic
        topicInput.value = topic;
        
        // Clear existing roles
        rolesContainer.innerHTML = '';
        
        // Add roles from example
        roles.forEach(role => {
            const inputGroup = document.createElement('div');
            inputGroup.className = 'input-group mb-2';
            
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'form-control role-input';
            input.placeholder = 'Role description';
            input.required = true;
            input.value = role;
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'btn btn-outline-danger remove-role-btn';
            removeBtn.type = 'button';
            removeBtn.innerHTML = '<i class="bi bi-trash"></i>';
            removeBtn.addEventListener('click', removeRoleInput);
            
            inputGroup.appendChild(input);
            inputGroup.appendChild(removeBtn);
            rolesContainer.appendChild(inputGroup);
        });
        
        // Update remove buttons
        updateRemoveButtons();
    }
    
    function showLoading(isLoading) {
        if (isLoading) {
            loadingIndicator.classList.remove('d-none');
            actionItemsContainer.classList.add('d-none');
            generateBtn.disabled = true;
            generateWithDocBtn.disabled = true;
        } else {
            loadingIndicator.classList.add('d-none');
            generateBtn.disabled = false;
            // ドキュメントがアップロードされている場合のみ有効化
            generateWithDocBtn.disabled = !sessionStorage.getItem('uploadedDocument');
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
        // コンテナをクリア
        errorMessage.innerHTML = '';
        
        // メインメッセージを追加
        const mainMsg = document.createElement('div');
        mainMsg.textContent = message;
        errorMessage.appendChild(mainMsg);
        
        // エラータイプに基づいた追加情報
        let helpText = document.createElement('div');
        helpText.className = 'mt-2 small';
        
        // APIキーエラーの場合
        if (message.includes('APIキー') || message.includes('API key') || message.includes('認証エラー')) {
            helpText.innerHTML = '<strong>APIキーの問題:</strong> Google Gemini APIキーが必要です。<a href="https://ai.google.dev/tutorials/setup" target="_blank">こちら</a>から取得して、プロジェクトの環境変数に設定してください。';
        }
        // クォータ制限エラーの場合
        else if (message.includes('リクエスト制限') || message.includes('quota') || message.includes('429')) {
            helpText.innerHTML = '<strong>API制限エラー:</strong> Google Gemini APIの無料枠制限に達しました。時間をおいて再試行するか、新しいプロジェクトでAPIキーを取得してください。';
        }
        // メモリ/リソースエラーの場合
        else if (message.includes('リソース制限') || message.includes('memory')) {
            helpText.innerHTML = '<strong>リソース制限:</strong> 役割の数やターン数を減らして再試行してください。多すぎるとメモリ不足になる可能性があります。';
        }
        // その他のエラー
        else {
            helpText.innerHTML = '<strong>エラー詳細:</strong> サーバーでエラーが発生しました。別のトピックや設定で再試行してください。';
        }
        
        errorMessage.appendChild(helpText);
        errorDisplay.classList.remove('d-none');
        
        // エラーログ
        console.error('Error generating discussion:', message);
    }
    
    function hideError() {
        errorDisplay.classList.add('d-none');
    }
    
    function enableExportButtons() {
        exportTextBtn.disabled = false;
        copyTextBtn.disabled = false;
        generateActionItemsBtn.disabled = false;
    }
    
    function exportDiscussion() {
        const discussionText = getDiscussionText();
        const topic = topicInput.value.trim();
        
        // Create a blob with the text
        const blob = new Blob([discussionText], { type: 'text/plain' });
        
        // Create a download link
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `discussion-${topic.replace(/\s+/g, '-').toLowerCase()}.txt`;
        
        // Trigger download
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    function copyDiscussion() {
        const discussionText = getDiscussionText();
        
        // Copy to clipboard
        navigator.clipboard.writeText(discussionText)
            .then(() => {
                // Show success notification
                const copyBtn = document.getElementById('copyText');
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="bi bi-check"></i> Copied!';
                
                // Reset button after 2 seconds
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                }, 2000);
            })
            .catch(err => {
                console.error('Failed to copy text: ', err);
                showError('Failed to copy to clipboard');
            });
    }
    
    function getDiscussionText() {
        const topic = discussionTopicHeader.textContent.replace('ディスカッション: ', '');
        let text = `Discussion Topic: ${topic}\n\n`;
        
        // Get all messages
        const bubbles = discussionContainer.querySelectorAll('.discussion-bubble');
        bubbles.forEach(bubble => {
            const role = bubble.querySelector('.role-tag').textContent;
            const content = bubble.querySelector('.message-content').textContent;
            
            text += `${role}:\n${content}\n\n`;
        });
        
        return text;
    }
    
    // ドキュメントアップロード関連の機能
    function handleDocumentUpload(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('documentFile');
        const file = fileInput.files[0];
        
        if (!file) {
            showDocumentError('ファイルを選択してください。');
            return;
        }
        
        // 5MBの制限を設定
        if (file.size > 5 * 1024 * 1024) {
            showDocumentError('ファイルサイズは5MB以下にしてください。');
            return;
        }
        
        // サポートされているファイル形式をチェック
        const validExtensions = ['.pdf', '.txt', '.docx'];
        const fileName = file.name.toLowerCase();
        const isValidExtension = validExtensions.some(ext => fileName.endsWith(ext));
        
        if (!isValidExtension) {
            showDocumentError('サポートされているファイル形式は PDF, TXT, DOCX のみです。');
            return;
        }
        
        // FormDataを作成
        const formData = new FormData();
        formData.append('document', file);
        
        // アップロードインジケータを表示
        const uploadBtn = document.getElementById('uploadDocumentBtn');
        const originalText = uploadBtn.innerHTML;
        uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> アップロード中...';
        uploadBtn.disabled = true;
        hideDocumentError();
        hideDocumentSuccess();
        
        // APIへのアップロード
        fetch('/upload-document', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'ドキュメントの処理中にエラーが発生しました。');
                });
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
        // セッションからドキュメント情報を削除
        sessionStorage.removeItem('uploadedDocument');
        
        // UI表示をリセット
        documentInfo.classList.add('d-none');
        hideDocumentSuccess();
        
        // ドキュメントを使用したディスカッション生成を無効化
        generateWithDocBtn.disabled = true;
        
        // ファイル入力をリセット
        document.getElementById('documentFile').value = '';
        
        // サーバーにもセッション削除を通知
        fetch('/clear-document', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                console.error('Failed to clear document session on server');
            }
        })
        .catch(error => {
            console.error('Error clearing document session:', error);
        });
    }
    
    function checkDocumentSession() {
        // セッションからドキュメント情報を取得
        const documentInfo = sessionStorage.getItem('uploadedDocument');
        
        if (documentInfo) {
            try {
                const docData = JSON.parse(documentInfo);
                updateDocumentInfo(docData.name);
                generateWithDocBtn.disabled = false;
            } catch (e) {
                console.error('Error parsing document session:', e);
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
        
        // タイムアウト処理を追加
        const timeoutDuration = 180000; // 180秒 (ドキュメント処理は通常より時間がかかる可能性がある)
        let timeoutId;
        
        const timeoutPromise = new Promise((_, reject) => {
            timeoutId = setTimeout(() => {
                reject(new Error('リクエストがタイムアウトしました。少ないロール数やターン数で再試行してください。'));
            }, timeoutDuration);
        });
        
        // リクエスト送信
        const fetchPromise = fetch('/generate-discussion-with-document', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        // リクエストとタイムアウトを競合
        Promise.race([fetchPromise, timeoutPromise])
            .then(response => {
                clearTimeout(timeoutId);
                
                // レスポンス処理は通常のディスカッション生成と同様
                if (!response.ok) {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json().then(errorData => {
                            throw new Error(errorData.error || `サーバーエラー: ${response.status}`);
                        });
                    } else {
                        return response.text().then(errorText => {
                            if (errorText.includes('<html>')) {
                                throw new Error(`サーバー内部エラー: リソース制限に達しました。少ないターン数でお試しください。`);
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
                actionItemsContent.innerHTML = data.markdown_content;
                
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
});
