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
    
    // 新機能用のDOM要素
    const summarizeDiscussionBtn = document.getElementById('summarizeDiscussion');
    const continueDiscussionBtn = document.getElementById('continueDiscussion');
    const provideGuidanceBtn = document.getElementById('provideGuidance');
    const summaryContainer = document.getElementById('summaryContainer');
    const summaryContent = document.getElementById('summaryContent');
    const guidanceContainer = document.getElementById('guidanceContainer');
    const guidanceContent = document.getElementById('guidanceContent');
    
    // モーダル関連
    const continueDiscussionModal = new bootstrap.Modal(document.getElementById('continueDiscussionModal'));
    const provideGuidanceModal = new bootstrap.Modal(document.getElementById('provideGuidanceModal'));
    const additionalTurnsInput = document.getElementById('additionalTurns');
    const useDocumentForContinuationCheckbox = document.getElementById('useDocumentForContinuation');
    const guidanceInstructionInput = document.getElementById('guidanceInstruction');
    const startContinueDiscussionBtn = document.getElementById('startContinueDiscussion');
    const startProvideGuidanceBtn = document.getElementById('startProvideGuidance');

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
        
        // 新機能のイベントリスナー
        summarizeDiscussionBtn.addEventListener('click', summarizeDiscussion);
        continueDiscussionBtn.addEventListener('click', showContinueDiscussionModal);
        provideGuidanceBtn.addEventListener('click', showProvideGuidanceModal);
        startContinueDiscussionBtn.addEventListener('click', handleContinueDiscussion);
        startProvideGuidanceBtn.addEventListener('click', handleProvideGuidance);
        
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
        
        // Get selected language
        const language = document.getElementById('language').value;
        
        // ボタンを無効化
        exportTextBtn.disabled = true;
        copyTextBtn.disabled = true;
        generateActionItemsBtn.disabled = true;
        summarizeDiscussionBtn.disabled = true;
        continueDiscussionBtn.disabled = true;
        provideGuidanceBtn.disabled = true;
        
        // 状態を初期化
        currentDiscussion = [];
        let currentTurn = 0;
        let currentRoleIndex = 0;
        
        // ターンごとに生成する処理を開始
        // 注意：実際のUIの初期化は generateNextTurn の初回実行時に行われる
        generateNextTurn(topic, roles, numTurns, currentDiscussion, currentTurn, currentRoleIndex, language);
    }
    
    function generateNextTurn(topic, roles, numTurns, discussion, currentTurn, currentRoleIndex, language) {
        // ステータス更新
        const totalRoles = roles.length;
        const totalIterations = numTurns * totalRoles;
        const currentIteration = (currentTurn * totalRoles) + currentRoleIndex + 1;
        const percent = Math.round((currentIteration / totalIterations) * 100);
        
        // 初回表示時のみディスカッションセクションを初期化
        if (currentIteration === 1) {
            // ディスカッションセクションを初期化
            discussionContainer.innerHTML = '';
            discussionTopicHeader.textContent = topic;
            discussionContainer.classList.remove('d-none');
            
            // コンテナを初期化
            actionItemsContainer.classList.add('d-none');
            summaryContainer.classList.add('d-none');
            guidanceContainer.classList.add('d-none');
        }
        
        // ロード表示を更新
        loadingIndicator.querySelector('.progress-bar').style.width = `${percent}%`;
        loadingIndicator.querySelector('.progress-bar').setAttribute('aria-valuenow', percent);
        loadingIndicator.querySelector('.progress-text').textContent = 
            `${roles[currentRoleIndex]}の発言を生成中... (${currentIteration}/${totalIterations})`;
        
        // リクエストデータを準備
        const requestData = {
            topic: topic,
            roles: roles,
            numTurns: numTurns,
            discussion: discussion,
            currentTurn: currentTurn,
            currentRoleIndex: currentRoleIndex,
            language: language
        };
        
        // サーバーに次のターンを要求
        fetch('/generate-next-turn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
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
            if (data.error) {
                showLoading(false);
                showError(data.error);
                return;
            }
            
            // 新しいメッセージを追加
            const newMessage = data.message;
            discussion.push(newMessage);
            
            // UIに表示（個別に発言表示）
            appendMessage(newMessage);
            
            // 全ての会話が終了したか確認
            if (data.is_complete) {
                // 処理終了
                showLoading(false);
                currentDiscussion = discussion;
                enableExportButtons();
                
                // 関連ボタンを有効化
                generateActionItemsBtn.disabled = false;
                summarizeDiscussionBtn.disabled = false;
                continueDiscussionBtn.disabled = false;
                provideGuidanceBtn.disabled = false;
            } else {
                // 次のターンを生成（ディレイを追加して順番に表示されていることを強調）
                setTimeout(() => {
                    generateNextTurn(
                        topic, 
                        roles, 
                        numTurns, 
                        discussion, 
                        data.next_turn, 
                        data.next_role_index,
                        language
                    );
                }, 500); // ディレイを500msに増やして表示の間隔を明確にする
            }
        })
        .catch(error => {
            showLoading(false);
            let errorMsg = error.message || 'ディスカッションの生成中にエラーが発生しました';
            showError(errorMsg);
            console.error('Error generating discussion:', error);
        });
    }
    
    function displayDiscussion(discussion, topic, isContinuation = false) {
        // 継続の場合は既存の内容をクリアしない
        if (!isContinuation) {
            discussionContainer.innerHTML = '';
            discussionContainer.classList.remove('discussion-continued');
        } else {
            discussionContainer.classList.add('discussion-continued');
        }
        
        // 継続マーカーが必要かどうかを確認
        const needsContinuationMarker = isContinuation && 
                                      discussionContainer.querySelectorAll('.discussion-bubble').length > 0;
        
        // 継続マーカーの追加
        if (needsContinuationMarker) {
            const continuationMarker = document.createElement('div');
            continuationMarker.className = 'continuation-marker my-4 py-2 text-center bg-info bg-opacity-25 rounded border border-info';
            continuationMarker.innerHTML = `
                <div class="fw-bold">＜ 議論継続部分 ＞</div>
                <div class="small text-muted">指導または継続機能による追加発言</div>
            `;
            discussionContainer.appendChild(continuationMarker);
        }
        
        // 新しい発言を追加（リアルタイムに表示できるよう1つ1つ処理）
        const startIndex = isContinuation ? discussionContainer.querySelectorAll('.discussion-bubble').length : 0;
        
        for (let i = startIndex; i < discussion.length; i++) {
            const msg = discussion[i];
            const isEven = i % 2 === 0;
            const isSystem = msg.role === 'システム';
            
            // システムメッセージは特別な形式で表示
            if (isSystem) {
                const systemMsg = document.createElement('div');
                systemMsg.className = 'system-message my-3 py-2 px-3 bg-warning bg-opacity-10 rounded border border-warning';
                systemMsg.innerHTML = `
                    <div class="fw-bold mb-1">システムメッセージ</div>
                    <div class="system-content">${markdownToHtml(msg.content)}</div>
                `;
                discussionContainer.appendChild(systemMsg);
                
                // 最新のメッセージが見えるようにスクロール
                systemMsg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                continue; // システムメッセージを処理したらループの次の反復へ
            }
            
            // 通常のメッセージバブル
            const bubble = document.createElement('div');
            bubble.className = `discussion-bubble ${isEven ? 'left' : 'right'} mb-3`;
            
            bubble.innerHTML = `
                <div class="role-tag">${msg.role}</div>
                <div class="message-content">${markdownToHtml(msg.content)}</div>
            `;
            
            discussionContainer.appendChild(bubble);
            
            // 最新のメッセージが見えるようにスクロール
            bubble.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        
        // コンテナのリセット
        actionItemsContainer.classList.add('d-none');
        summaryContainer.classList.add('d-none');
        guidanceContainer.classList.add('d-none');
        
        // スクロール処理
        setTimeout(() => {
            if (isContinuation && needsContinuationMarker) {
                // 継続議論の場合、継続マーカーの位置にスクロール
                const continuationMarker = discussionContainer.querySelector('.continuation-marker');
                if (continuationMarker) {
                    continuationMarker.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            } else if (!isContinuation) {
                // 新規議論の場合、議論コンテナの先頭へスクロール
                discussionContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 200);
        
        // ディスカッション関連ボタンの有効化
        generateActionItemsBtn.disabled = false;
        summarizeDiscussionBtn.disabled = false;
        continueDiscussionBtn.disabled = false;
        provideGuidanceBtn.disabled = false;
        
        // 他のエクスポートボタンも有効化
        enableExportButtons();
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
        
        // ファイル保存用のドロップダウンボタンも有効化
        document.getElementById('saveFileDropdown').disabled = false;
        
        // ファイル保存用のボタン群も有効化
        const saveButtons = document.querySelectorAll('.save-file-btn');
        saveButtons.forEach(button => {
            button.disabled = false;
        });
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
    
    // サーバーサイドでファイルとして保存する関数
    function saveDiscussionToFile(format) {
        showLoading(true);
        
        // 現在の議論データと議題を取得
        const discussionData = currentDiscussion;
        const topic = document.getElementById('topic').value;
        
        if (!discussionData || discussionData.length === 0) {
            showError('保存する議論データがありません。');
            showLoading(false);
            return;
        }
        
        // APIリクエストの作成
        fetch('/save-discussion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                discussion_data: discussionData,
                topic: topic,
                format: format
            })
        })
        .then(response => response.json())
        .then(data => {
            showLoading(false);
            
            if (data.error) {
                showError(data.error);
                return;
            }
            
            // ダウンロードリンクの作成と自動クリック
            const a = document.createElement('a');
            a.href = data.url;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            
            setTimeout(function() {
                document.body.removeChild(a);
            }, 100);
        })
        .catch(error => {
            showLoading(false);
            showError('ファイル保存中にエラーが発生しました: ' + error.message);
            console.error('Error saving discussion:', error);
        });
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
    
    function appendMessage(message) {
        const messageCount = discussionContainer.children.length;
        const isEven = messageCount % 2 === 0;
        
        const bubble = document.createElement('div');
        bubble.className = `discussion-bubble ${isEven ? 'left' : 'right'} mb-3`;
        
        // content内のマークダウンをHTMLに変換（シンプルな実装）
        const contentHtml = markdownToHtml(message.content);
        
        bubble.innerHTML = `
            <div class="role-tag">${message.role}</div>
            <div class="message-content markdown-content">${contentHtml}</div>
        `;
        
        discussionContainer.appendChild(bubble);
        
        // スクロールを最新のメッセージに合わせる
        bubble.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
        
        // Get selected language
        const language = document.getElementById('language').value;
        
        // ボタンを無効化
        exportTextBtn.disabled = true;
        copyTextBtn.disabled = true;
        generateActionItemsBtn.disabled = true;
        summarizeDiscussionBtn.disabled = true;
        continueDiscussionBtn.disabled = true;
        provideGuidanceBtn.disabled = true;
        
        // 状態を初期化
        currentDiscussion = [];
        let currentTurn = 0;
        let currentRoleIndex = 0;
        
        // ドキュメント参照を使用するフラグをセット
        const useDocument = true;
        
        // ターンごとに生成する処理
        generateNextTurnWithDocument(topic, roles, numTurns, currentDiscussion, currentTurn, currentRoleIndex, language, useDocument);
    }
    
    function generateNextTurnWithDocument(topic, roles, numTurns, discussion, currentTurn, currentRoleIndex, language, useDocument) {
        // ステータス更新
        const totalRoles = roles.length;
        const totalIterations = numTurns * totalRoles;
        const currentIteration = (currentTurn * totalRoles) + currentRoleIndex + 1;
        const percent = Math.round((currentIteration / totalIterations) * 100);
        
        // 初回表示時のみディスカッションセクションを初期化
        if (currentIteration === 1) {
            // ディスカッションセクションを初期化
            discussionContainer.innerHTML = '';
            discussionTopicHeader.textContent = `${topic} (文書参照)`;
            discussionContainer.classList.remove('d-none');
            
            // コンテナを初期化
            actionItemsContainer.classList.add('d-none');
            summaryContainer.classList.add('d-none');
            guidanceContainer.classList.add('d-none');
        }
        
        // ロード表示を更新
        loadingIndicator.querySelector('.progress-bar').style.width = `${percent}%`;
        loadingIndicator.querySelector('.progress-bar').setAttribute('aria-valuenow', percent);
        loadingIndicator.querySelector('.progress-text').textContent = 
            `${roles[currentRoleIndex]}の発言を生成中... (文書参照) (${currentIteration}/${totalIterations})`;
        
        // リクエストデータを準備
        const requestData = {
            topic: topic,
            roles: roles,
            numTurns: numTurns,
            discussion: discussion,
            currentTurn: currentTurn,
            currentRoleIndex: currentRoleIndex,
            language: language,
            use_document: useDocument
        };
        
        // サーバーに次のターンを要求
        fetch('/generate-next-turn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
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
            if (data.error) {
                showLoading(false);
                showError(data.error);
                return;
            }
            
            // 新しいメッセージを追加
            const newMessage = data.message;
            discussion.push(newMessage);
            
            // UIに表示（個別に発言表示）
            appendMessage(newMessage);
            
            // 全ての会話が終了したか確認
            if (data.is_complete) {
                // 処理終了
                showLoading(false);
                currentDiscussion = discussion;
                enableExportButtons();
                
                // 関連ボタンを有効化
                generateActionItemsBtn.disabled = false;
                summarizeDiscussionBtn.disabled = false;
                continueDiscussionBtn.disabled = false;
                provideGuidanceBtn.disabled = false;
            } else {
                // 次のターンを生成
                setTimeout(() => {
                    generateNextTurnWithDocument(
                        topic, 
                        roles, 
                        numTurns, 
                        discussion, 
                        data.next_turn, 
                        data.next_role_index,
                        language,
                        useDocument
                    );
                }, 500); // ディレイを500msに増やして表示の間隔を明確にする
            }
        })
        .catch(error => {
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
        summaryContainer.classList.add('d-none');
        guidanceContainer.classList.add('d-none');
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
                
                // アクションアイテムコンテナへスクロール
                setTimeout(() => {
                    actionItemsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 200);
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
    
    // 議論の要約機能
    function summarizeDiscussion() {
        // ディスカッションデータがあることを確認
        const bubbles = discussionContainer.querySelectorAll('.discussion-bubble');
        if (bubbles.length === 0) {
            showError('要約するためのディスカッションデータがありません。');
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
        
        // 言語設定を取得
        const language = document.getElementById('language').value;
        
        // トピックを取得
        const topic = discussionTopicHeader.textContent.replace('ディスカッション: ', '');
        
        // ローディング表示
        showLoading(true);
        hideError();
        
        // コンテナ表示設定
        actionItemsContainer.classList.add('d-none');
        summaryContainer.classList.remove('d-none');
        guidanceContainer.classList.add('d-none');
        summaryContent.innerHTML = '<div class="text-center"><p>議論の要約を生成中...</p></div>';
        
        // タイムアウト処理
        const timeoutDuration = 60000; // 60秒
        let timeoutId;
        
        const timeoutPromise = new Promise((_, reject) => {
            timeoutId = setTimeout(() => {
                reject(new Error('要約生成がタイムアウトしました。'));
            }, timeoutDuration);
        });
        
        // リクエスト送信
        const fetchPromise = fetch('/summarize-discussion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                discussion_data: discussionData,
                topic: topic,
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
                                throw new Error(`サーバー内部エラー: 要約生成中にエラーが発生しました。`);
                            } else {
                                throw new Error(`サーバーエラー: ${response.status} - ${errorText.slice(0, 100)}`);
                            }
                        });
                    }
                }
                
                return response.json();
            })
            .then(data => {
                showLoading(false);
                
                if (data.error) {
                    showError(data.error);
                    summaryContainer.classList.add('d-none');
                    return;
                }
                
                // MarkdownをHTMLに変換
                summaryContent.innerHTML = markdownToHtml(data.markdown_content);
                
                // スクロールして表示
                setTimeout(() => {
                    summaryContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 200);
            })
            .catch(error => {
                clearTimeout(timeoutId);
                showLoading(false);
                summaryContainer.classList.add('d-none');
                
                let errorMsg = error.message || '要約の生成中にエラーが発生しました';
                showError(errorMsg);
                console.error('Error summarizing discussion:', error);
            });
    }
    
    // 議論継続のモーダル表示
    function showContinueDiscussionModal() {
        // ディスカッションデータがあることを確認
        const bubbles = discussionContainer.querySelectorAll('.discussion-bubble');
        if (bubbles.length === 0) {
            showError('継続するためのディスカッションデータがありません。');
            return;
        }
        
        // 文書参照チェックボックスの状態を設定
        const hasDocument = !documentInfo.classList.contains('d-none');
        useDocumentForContinuationCheckbox.disabled = !hasDocument;
        if (!hasDocument) {
            useDocumentForContinuationCheckbox.checked = false;
        }
        
        // モーダルを表示
        continueDiscussionModal.show();
    }
    
    // 議論への指導・提案のモーダル表示
    function showProvideGuidanceModal() {
        // ディスカッションデータがあることを確認
        const bubbles = discussionContainer.querySelectorAll('.discussion-bubble');
        if (bubbles.length === 0) {
            showError('指導提供するためのディスカッションデータがありません。');
            return;
        }
        
        // インプットをクリア
        guidanceInstructionInput.value = '';
        
        // モーダルを表示
        provideGuidanceModal.show();
    }
    
    // 議論継続処理
    function handleContinueDiscussion() {
        // モーダルを閉じる
        continueDiscussionModal.hide();
        
        // フォームデータ取得
        const additionalTurns = parseInt(additionalTurnsInput.value);
        const useDocument = useDocumentForContinuationCheckbox.checked;
        
        // バリデーション
        if (additionalTurns < 1 || additionalTurns > 5) {
            showError('追加ターン数は1から5の間で指定してください。');
            return;
        }
        
        // 議論データを収集
        const discussionData = [];
        const bubbles = discussionContainer.querySelectorAll('.discussion-bubble');
        bubbles.forEach(bubble => {
            const role = bubble.querySelector('.role-tag').textContent;
            const content = bubble.querySelector('.message-content').textContent;
            
            discussionData.push({
                role: role,
                content: content
            });
        });
        
        // 役割の抽出（ユニークな役割のリストを作成）
        const roles = Array.from(new Set(discussionData.map(item => item.role)));
        
        // トピックを取得
        const topicFull = discussionTopicHeader.textContent;
        let topic = topicFull.replace('ディスカッション: ', '');
        if (topic.endsWith(' (文書参照)')) {
            topic = topic.replace(' (文書参照)', '');
        }
        
        // 言語設定を取得
        const language = document.getElementById('language').value;
        
        // ローディング表示
        showLoading(true);
        hideError();
        
        // 初期リクエストデータ作成（ターンごとに更新される）
        let requestData = {
            discussion_data: discussionData,
            topic: topic,
            roles: roles,
            num_additional_turns: additionalTurns,
            language: language,
            use_document: useDocument,
            current_turn: 0,  // 初期ターン
            current_role_index: 0  // 初期役割インデックス
        };
        
        // 継続議論のターンごとの処理を実行
        fetchNextContinuationTurn(requestData, discussionData);
    }
    
    // 継続議論の次のターンをフェッチする関数
    function fetchNextContinuationTurn(requestData, currentDiscussionData) {
        // 進行状況更新
        const totalRoles = requestData.roles.length;
        const totalIterations = requestData.num_additional_turns * totalRoles;
        const currentIteration = (requestData.current_turn * totalRoles) + requestData.current_role_index;
        const percent = Math.round((currentIteration / totalIterations) * 100);
        
        // ロード表示を更新
        loadingIndicator.querySelector('.progress-bar').style.width = `${percent}%`;
        loadingIndicator.querySelector('.progress-bar').setAttribute('aria-valuenow', percent);
        
        const roleIndex = requestData.current_role_index;
        const roleName = requestData.roles[roleIndex] || '参加者';
        
        loadingIndicator.querySelector('.progress-text').textContent = 
            `${roleName}の発言を生成中... (${currentIteration+1}/${totalIterations})` + 
            (requestData.use_document ? ' (文書参照)' : '');
        
        // リクエスト送信
        fetch('/continue-discussion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
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
                            throw new Error(`サーバー内部エラー: 議論継続中にエラーが発生しました。`);
                        } else {
                            throw new Error(`サーバーエラー: ${response.status} - ${errorText.slice(0, 100)}`);
                        }
                    });
                }
            }
            
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showLoading(false);
                showError(data.error);
                return;
            }
            
            // 最初のリクエスト（初期化）の場合は次のリクエストに進む
            if (!data.message) {
                // 次のリクエストのためにパラメータを更新
                requestData.current_turn = data.next_turn;
                requestData.current_role_index = data.next_role_index;
                
                // 次のターンを即時取得
                fetchNextContinuationTurn(requestData, currentDiscussionData);
                return;
            }
            
            // 新しいメッセージを追加
            currentDiscussionData.push(data.message);
            
            // UIに表示（個別に発言表示）
            appendMessage(data.message);
            
            // トピックヘッダーを更新
            if (requestData.use_document) {
                discussionTopicHeader.textContent = `ディスカッション: ${requestData.topic} (文書参照)`;
            } else {
                discussionTopicHeader.textContent = `ディスカッション: ${requestData.topic}`;
            }
            
            // すべての会話が終了したかどうかを確認
            if (data.is_complete) {
                // 処理終了
                showLoading(false);
                
                // 関連ボタンを有効化
                generateActionItemsBtn.disabled = false;
                summarizeDiscussionBtn.disabled = false;
                continueDiscussionBtn.disabled = false;
                provideGuidanceBtn.disabled = false;
                
                // エクスポートボタンを有効化
                enableExportButtons();
                

            } else {
                // 次のリクエストのためにパラメータを更新
                requestData.current_turn = data.next_turn;
                requestData.current_role_index = data.next_role_index;
                requestData.discussion_data = currentDiscussionData;
                
                // 次のターンを取得（ディレイを追加して順番に表示されていることを強調）
                setTimeout(() => {
                    fetchNextContinuationTurn(requestData, currentDiscussionData);
                }, 500);
            }
        })
        .catch(error => {
            showLoading(false);
            
            let errorMsg = error.message || '議論の継続中にエラーが発生しました';
            showError(errorMsg);
            console.error('Error continuing discussion:', error);
        });
    }
    
    // 指導に基づく議論継続処理
    function handleProvideGuidance() {
        // モーダルを閉じる
        provideGuidanceModal.hide();
        
        // フォームデータ取得
        const instruction = guidanceInstructionInput.value.trim();
        const numAdditionalTurns = parseInt(document.getElementById('guidanceAdditionalTurns').value);
        const useDocument = document.getElementById('useDocumentForGuidance').checked;
        
        // バリデーション
        if (!instruction) {
            showError('指導内容を入力してください。');
            return;
        }
        
        if (numAdditionalTurns < 1 || numAdditionalTurns > 5) {
            showError('追加ターン数は1から5の間で指定してください。');
            return;
        }
        
        // 議論データを収集
        const discussionData = [];
        const bubbles = discussionContainer.querySelectorAll('.discussion-bubble');
        bubbles.forEach(bubble => {
            const role = bubble.querySelector('.role-tag').textContent;
            const content = bubble.querySelector('.message-content').textContent;
            
            discussionData.push({
                role: role,
                content: content
            });
        });
        
        // トピックを取得
        const topicFull = discussionTopicHeader.textContent;
        let topic = topicFull.replace('ディスカッション: ', '');
        if (topic.endsWith(' (文書参照)')) {
            topic = topic.replace(' (文書参照)', '');
        }
        
        // 言語設定を取得
        const language = document.getElementById('language').value;
        
        // ローディング表示
        showLoading(true);
        hideError();
        
        // リクエストデータ作成
        const requestData = {
            discussion_data: discussionData,
            topic: topic,
            instruction: instruction,
            num_additional_turns: numAdditionalTurns,
            use_document: useDocument,
            language: language
        };
        
        // タイムアウト処理
        const timeoutDuration = 60000; // 60秒
        let timeoutId;
        
        const timeoutPromise = new Promise((_, reject) => {
            timeoutId = setTimeout(() => {
                reject(new Error('指導提供がタイムアウトしました。'));
            }, timeoutDuration);
        });
        
        // リクエスト送信
        const fetchPromise = fetch('/provide-guidance', {
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
                
                if (!response.ok) {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json().then(errorData => {
                            throw new Error(errorData.error || `サーバーエラー: ${response.status}`);
                        });
                    } else {
                        return response.text().then(errorText => {
                            if (errorText.includes('<html>')) {
                                throw new Error(`サーバー内部エラー: 指導提供中にエラーが発生しました。`);
                            } else {
                                throw new Error(`サーバーエラー: ${response.status} - ${errorText.slice(0, 100)}`);
                            }
                        });
                    }
                }
                
                return response.json();
            })
            .then(data => {
                showLoading(false);
                
                if (data.error) {
                    showError(data.error);
                    return;
                }
                
                // 現在のディスカッションを更新
                currentDiscussion = data.discussion;
                
                // 継続前のメッセージ数を記録
                const previousBubbleCount = discussionContainer.querySelectorAll('.discussion-bubble').length;
                
                // 議論表示を更新
                displayDiscussion(data.discussion, topic, true);
                
                // トピックヘッダーを更新
                if (useDocument) {
                    discussionTopicHeader.textContent = `ディスカッション: ${topic} (文書参照)`;
                } else {
                    discussionTopicHeader.textContent = `ディスカッション: ${topic}`;
                }
                
                // 指導・提案カードを非表示
                guidanceContainer.classList.add('d-none');
            })
            .catch(error => {
                clearTimeout(timeoutId);
                showLoading(false);
                guidanceContainer.classList.add('d-none');
                
                let errorMsg = error.message || '指導提供中にエラーが発生しました';
                showError(errorMsg);
                console.error('Error providing guidance for discussion:', error);
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
        
        // 太字とイタリック
        html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
        
        // コードブロック
        html = html.replace(/```([^`]+)```/gim, '<pre><code>$1</code></pre>');
        html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');
        
        // リスト（番号付き）
        html = html.replace(/^\d+\. (.*$)/gim, '<li>$1</li>');
        html = html.replace(/<\/li>\n<li>/gim, '</li><li>');
        html = html.replace(/(<li>.*<\/li>)/gim, '<ol>$1</ol>');
        
        // リスト（箇条書き）
        html = html.replace(/^- (.*$)/gim, '<li>$1</li>');
        html = html.replace(/^• (.*$)/gim, '<li>$1</li>');
        html = html.replace(/^・(.*$)/gim, '<li>$1</li>');
        
        // 水平線
        html = html.replace(/^---+$/gim, '<hr>');
        
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