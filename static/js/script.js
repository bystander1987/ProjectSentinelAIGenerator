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
    
    // 役割アップロード関連のDOM要素
    const uploadRolesBtn = document.getElementById('uploadRolesBtn');
    const rolesFileInput = document.getElementById('rolesFile');
    const clearExistingRolesCheckbox = document.getElementById('clearExistingRoles');
    const rolesPreviewContainer = document.getElementById('rolesPreviewContainer');
    const rolesUploadStatus = document.getElementById('rolesUploadStatus');
    const rolesUploadStatusMessage = document.getElementById('rolesUploadStatusMessage');
    const rolesUploadError = document.getElementById('rolesUploadError');
    const rolesUploadErrorMessage = document.getElementById('rolesUploadErrorMessage');
    const importRolesBtn = document.getElementById('importRolesBtn');
    
    // 詳細設定モーダル関連のDOM要素
    const modelSelect = document.getElementById('modelSelect');
    const temperatureSlider = document.getElementById('temperatureSlider');
    const temperatureValue = document.getElementById('temperatureValue');
    const maxOutputTokens = document.getElementById('maxOutputTokens');
    const saveSettingsSwitch = document.getElementById('saveSettingsSwitch');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    
    // モーダル関連
    const continueDiscussionModal = new bootstrap.Modal(document.getElementById('continueDiscussionModal'));
    const provideGuidanceModal = new bootstrap.Modal(document.getElementById('provideGuidanceModal'));
    const uploadRolesModal = new bootstrap.Modal(document.getElementById('uploadRolesModal'));
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
        
        // 役割アップロード関連のイベントリスナー
        rolesFileInput.addEventListener('change', handleRolesFileSelect);
        importRolesBtn.addEventListener('click', importRoles);
        
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
        
        // セッション間でデータが残らないように、ドキュメント分析結果をクリア
        const analysisContainer = document.getElementById('documentAnalysisContainer');
        if (analysisContainer) {
            analysisContainer.innerHTML = '';
        }
        
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
        
        // 現在の設定を取得
        const currentSettings = getCurrentSettingsFromUI();
        
        // リクエストデータを準備
        const requestData = {
            topic: topic,
            roles: roles,
            numTurns: numTurns,
            discussion: discussion,
            currentTurn: currentTurn,
            currentRoleIndex: currentRoleIndex,
            language: language,
            // モデル設定を追加
            model: currentSettings.model,
            temperature: currentSettings.temperature,
            maxOutputTokens: currentSettings.maxOutputTokens
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
            
            // ドキュメントが存在する場合、最初に表示
            if (document.getElementById('documentInfo').classList.contains('d-flex')) {
                // ドキュメントの内容を表示
                fetch('/get-document-text', {
                    method: 'GET'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.document_text) {
                        const documentCard = document.createElement('div');
                        documentCard.className = 'document-display card mb-4 border-info';
                        documentCard.innerHTML = `
                            <div class="card-header bg-info bg-opacity-25 d-flex justify-content-between align-items-center">
                                <strong><i class="bi bi-file-text"></i> アップロードされた文書内容</strong>
                                <button type="button" class="btn btn-sm btn-outline-info toggle-document-btn">
                                    <i class="bi bi-arrows-collapse"></i> 折りたたむ
                                </button>
                            </div>
                            <div class="card-body document-body">
                                <div class="document-content" style="max-height: 300px; overflow-y: auto; white-space: pre-wrap; font-size: 0.9rem;">${escapeHtml(data.document_text)}</div>
                            </div>
                        `;
                        discussionContainer.appendChild(documentCard);
                        
                        // 折りたたみボタンの機能を実装
                        const toggleBtn = documentCard.querySelector('.toggle-document-btn');
                        const docBody = documentCard.querySelector('.document-body');
                        toggleBtn.addEventListener('click', function() {
                            if (docBody.style.display === 'none') {
                                docBody.style.display = 'block';
                                toggleBtn.innerHTML = '<i class="bi bi-arrows-collapse"></i> 折りたたむ';
                            } else {
                                docBody.style.display = 'none';
                                toggleBtn.innerHTML = '<i class="bi bi-arrows-expand"></i> 展開する';
                            }
                        });
                        
                        // トピックヘッダーをディスカッション上部に設定
                        const topicHeader = document.createElement('div');
                        topicHeader.className = 'topic-header alert alert-primary mt-4';
                        topicHeader.innerHTML = `
                            <h5 class="mb-0">ディスカッション: ${topic}</h5>
                            <p class="mb-0 small">文書に基づいたディスカッションを開始します</p>
                        `;
                        discussionContainer.appendChild(topicHeader);
                    }
                })
                .catch(error => {
                    console.error("文書内容の取得中にエラー:", error);
                });
            }
        } else {
            discussionContainer.classList.add('discussion-continued');
        }
        
        // トピックヘッダーを表示セクションに設定
        discussionTopicHeader.textContent = `ディスカッション: ${topic}`;
        
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
            const isConsultant = msg.role === 'コンサルタント';
            
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
            
            // コンサルタントの分析は特別なスタイルで表示
            if (isConsultant) {
                const consultantMsg = document.createElement('div');
                consultantMsg.className = 'consultant-message my-4 py-3 px-4 bg-info bg-opacity-10 rounded border border-info';
                consultantMsg.innerHTML = `
                    <div class="d-flex align-items-center mb-2">
                        <i class="bi bi-graph-up me-2"></i>
                        <div class="fw-bold">コンサルタント分析</div>
                    </div>
                    <div class="consultant-content">${markdownToHtml(msg.content)}</div>
                `;
                discussionContainer.appendChild(consultantMsg);
                
                // 最新のメッセージが見えるようにスクロール
                consultantMsg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                continue; // コンサルタントメッセージを処理したらループの次の反復へ
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
    
    function addRoleInput(roleText = '') {
        const roleInputs = document.querySelectorAll('.role-input');
        
        if (roleInputs.length >= 6) {
            showError('最大6つまでの役割を設定できます');
            return;
        }
        
        const div = document.createElement('div');
        div.className = 'input-group mb-2 role-input-group';
        div.innerHTML = `
            <input type="text" class="form-control role-input" placeholder="役割の説明" value="${escapeHtml(roleText)}" required>
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
            div.className = 'input-group mb-2 role-input-group';
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
            generateWithDocBtn.disabled = !document.getElementById('documentInfo').classList.contains('d-flex');
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
    
    // 役割ファイルのアップロード処理関数
    function handleRolesFileSelect(e) {
        const file = e.target.files[0];
        
        if (!file) {
            return;
        }
        
        // プレビューをリセット
        rolesPreviewContainer.innerHTML = '<div class="text-center"><i class="bi bi-arrow-repeat spin"></i> ファイルを読み込み中...</div>';
        
        // インポートボタンを無効化（プレビュー確認まで）
        importRolesBtn.disabled = true;
        
        // ステータスとエラー表示をリセット
        rolesUploadStatus.classList.add('d-none');
        rolesUploadError.classList.add('d-none');
        
        // JSONファイルの場合は、サーバー側の処理を使用
        const fileExt = file.name.split('.').pop().toLowerCase();
        if (fileExt === 'json') {
            // FormDataの作成
            const formData = new FormData();
            formData.append('file', file);
            
            // サーバーにファイルをアップロード
            fetch('/process-json-file', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`サーバーエラー: ${response.status}`);
                }
                return response.json();
            })
            .then(result => {
                console.log("Server processed JSON:", result);
                
                if (result.success) {
                    // 成功した場合、データを処理
                    const data = result.data;
                    const includesTopic = document.getElementById('includesTopicSwitch').checked;
                    let roles = [];
                    let topic = null;
                    
                    if (includesTopic && data.topic && Array.isArray(data.roles)) {
                        // テーマと役割が含まれる形式: {"topic": "テーマ", "roles": [{name, description}, ...]}
                        topic = data.topic;
                        roles = data.roles.map(role => ({
                            name: role.name || '',
                            description: role.description || ''
                        }));
                    } else if (Array.isArray(data)) {
                        // 役割のみの配列: [{name, description}, ...]
                        roles = data.map(role => ({
                            name: role.name || '',
                            description: role.description || ''
                        }));
                    } else if (typeof data === 'object') {
                        // その他のオブジェクト形式
                        throw new Error('サポートされていないJSON形式です。説明に記載された形式に従ってください。');
                    } else {
                        throw new Error('無効なJSON形式です。説明に記載された形式に従ってください。');
                    }
                    
                    // 空の役割名や説明がある場合は除外
                    roles = roles.filter(role => role.name.trim() !== '');
                    
                    if (roles.length === 0) {
                        throw new Error('有効な役割が見つかりませんでした。ファイル形式を確認してください。');
                    }
                    
                    // 役割のプレビューを表示
                    displayRolesPreview({ roles, topic });
                    
                    // インポートボタンを有効化
                    importRolesBtn.disabled = false;
                } else {
                    // エラーの場合
                    throw new Error(result.error || 'ファイルの処理に失敗しました。');
                }
            })
            .catch(error => {
                // エラー処理
                rolesPreviewContainer.innerHTML = '<p class="text-muted text-center my-2">プレビューを表示できません</p>';
                rolesUploadErrorMessage.textContent = error.message;
                rolesUploadError.classList.remove('d-none');
                console.error('Error processing JSON file:', error);
            });
            return;
        }
        
        // ファイルの種類に基づいて処理を分岐（JSON以外）
        
        // 処理関数の定義（エンコーディング試行用）
        const processFile = function(content) {
            try {
                let result;
                
                // ファイル形式に応じた処理
                if (fileExt === 'json') {
                    // JSONファイルの処理
                    result = parseRolesJson(content);
                } else if (fileExt === 'csv') {
                    // CSVファイルの処理
                    result = parseRolesCsv(content);
                } else if (fileExt === 'txt') {
                    // テキストファイルの処理
                    result = parseRolesTxt(content);
                } else {
                    throw new Error(`サポートされていないファイル形式です: ${fileExt}`);
                }
                
                // 少なくとも1つ以上の役割があることを確認
                if (result.roles.length === 0) {
                    throw new Error('有効な役割が見つかりませんでした。ファイル形式を確認してください。');
                }
                
                // 役割のプレビューを表示
                displayRolesPreview(result);
                
                // インポートボタンを有効化
                importRolesBtn.disabled = false;
                
                // 処理成功
                return true;
            } catch (error) {
                console.error('Error processing file with current encoding:', error);
                return false;
            }
        };
        
        // まずバイナリとして読み込み、エンコーディングを判断
        const binaryReader = new FileReader();
        binaryReader.onload = function(event) {
            const content = new Uint8Array(event.target.result);
            
            // エンコーディングの検出を試みる
            let encoding = 'utf-8'; // デフォルト
            
            // BOMの検出
            if (content.length >= 3 && content[0] === 0xEF && content[1] === 0xBB && content[2] === 0xBF) {
                encoding = 'utf-8'; // UTF-8 with BOM
            } 
            // Shift-JISの特徴的なバイトパターンを検出
            else if (content.some(byte => (byte >= 0x81 && byte <= 0x9F) || (byte >= 0xE0 && byte <= 0xEF))) {
                encoding = 'shift-jis';
            }
            
            console.log(`Detected encoding: ${encoding}`);
            
            // テキストとして再読み込み
            const textReader = new FileReader();
            textReader.onload = function(e) {
                let success = processFile(e.target.result);
                
                // UTF-8で失敗した場合、Shift-JISで再試行
                if (!success && encoding === 'utf-8') {
                    console.log("Retrying with Shift-JIS encoding");
                    const sjisReader = new FileReader();
                    sjisReader.onload = function(e2) {
                        success = processFile(e2.target.result);
                        
                        // それでも失敗した場合
                        if (!success) {
                            // エラー処理
                            rolesPreviewContainer.innerHTML = '<p class="text-muted text-center my-2">プレビューを表示できません</p>';
                            rolesUploadErrorMessage.textContent = 'ファイルの解析に失敗しました。ファイル形式とエンコーディングを確認してください。';
                            rolesUploadError.classList.remove('d-none');
                        }
                    };
                    sjisReader.onerror = handleFileReadError;
                    sjisReader.readAsText(file, 'shift-jis');
                }
                // 最初からShift-JISで失敗した場合、EUC-JPで再試行
                else if (!success && encoding === 'shift-jis') {
                    console.log("Retrying with EUC-JP encoding");
                    const eucReader = new FileReader();
                    eucReader.onload = function(e2) {
                        success = processFile(e2.target.result);
                        
                        // それでも失敗した場合
                        if (!success) {
                            // エラー処理
                            rolesPreviewContainer.innerHTML = '<p class="text-muted text-center my-2">プレビューを表示できません</p>';
                            rolesUploadErrorMessage.textContent = 'ファイルの解析に失敗しました。ファイル形式とエンコーディングを確認してください。';
                            rolesUploadError.classList.remove('d-none');
                        }
                    };
                    eucReader.onerror = handleFileReadError;
                    eucReader.readAsText(file, 'euc-jp');
                }
            };
            textReader.onerror = handleFileReadError;
            textReader.readAsText(file, encoding);
        };
        
        // エラーハンドラ
        const handleFileReadError = function(error) {
            rolesPreviewContainer.innerHTML = '<p class="text-muted text-center my-2">ファイルの読み込みに失敗しました</p>';
            rolesUploadErrorMessage.textContent = 'ファイルの読み込み中にエラーが発生しました。';
            rolesUploadError.classList.remove('d-none');
            console.error('Error reading file:', error);
        };
        
        binaryReader.onerror = handleFileReadError;
        
        // まずバイナリとして読み込む
        binaryReader.readAsArrayBuffer(file);

    }
    
    // JSON形式の役割ファイルをパースする
    function parseRolesJson(content) {
        try {
            // 文字化け対策：コンソールに内容を出力（デバッグ用）
            console.log("Content first 100 chars:", content.substring(0, 100));
            
            // エンコーディングの問題を検出して修正を試みる
            // BOMを削除
            const contentWithoutBOM = content.replace(/^\uFEFF/, '');
            
            // 特殊な文字や改行、タブなどの処理
            const sanitizedContent = contentWithoutBOM
                .replace(/\r\n/g, '\n')  // Windows改行をUnix改行に統一
                .replace(/\r/g, '\n')    // Mac改行をUnix改行に統一
                .replace(/\t/g, ' ')     // タブをスペースに変換
                .replace(/\\/g, '\\\\')  // バックスラッシュをエスケープ
                .replace(/\\"/g, '\\"')  // 引用符をエスケープ
                .trim();                 // 前後の空白を削除
                
            console.log("Sanitized content first 100 chars:", sanitizedContent.substring(0, 100));
            
            // JSONパースを試みる
            let data;
            try {
                // 最初に標準的なJSONパースを試みる
                data = JSON.parse(sanitizedContent);
                console.log("Standard JSON parse successful");
            } catch (e) {
                // 日本語文字が原因でJSONパースに失敗した可能性がある場合の対応
                console.error("Initial JSON parse failed:", e);
                
                try {
                    // JSONの形式を修正してみる
                    let fixedContent = sanitizedContent;
                    
                    // トリプルバイト文字（日本語など）の処理
                    const hasJapanese = /[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]/.test(fixedContent);
                    
                    if (hasJapanese) {
                        console.log("Japanese characters detected, attempting specialized parsing");
                        
                        // 一度eval経由で評価してみる（セキュリティ的にはよくない方法だが、クライアントサイドでの一時的な処理として例外的に使用）
                        try {
                            // evalを安全に使うための工夫：JavaScriptオブジェクトリテラルとして評価
                            fixedContent = fixedContent.replace(/([{,]\s*)(['"])?([a-zA-Z0-9_]+)(['"])?\s*:/g, '$1"$3":');
                            const jsonStr = `(${fixedContent})`;
                            data = eval(jsonStr);
                            console.log("Eval-based parse successful");
                        } catch (evalError) {
                            console.error("Eval parse failed:", evalError);
                            
                            // 最後の手段：テキスト置換
                            try {
                                // 不正な引用符を修正
                                fixedContent = sanitizedContent
                                    .replace(/"/g, '"')        // スマートクォートを通常の引用符に変換
                                    .replace(/"/g, '"')        // スマートクォートを通常の引用符に変換
                                    .replace(/'/g, "'")        // スマートアポストロフィを通常のアポストロフィに変換
                                    .replace(/'/g, "'");       // スマートアポストロフィを通常のアポストロフィに変換
                                
                                data = JSON.parse(fixedContent);
                                console.log("Character replacement parse successful");
                            } catch (e3) {
                                console.error("All parsing attempts failed:", e3);
                                throw new Error('JSONの解析に失敗しました。ファイル形式を確認してください。');
                            }
                        }
                    } else {
                        throw new Error('JSONの解析に失敗しました。ファイルが有効なJSON形式であることを確認してください。');
                    }
                } catch (e2) {
                    console.error("All JSON parse attempts failed:", e2);
                    throw new Error('JSONの解析に失敗しました。ファイルの形式とエンコーディングを確認してください。');
                }
            }
            
            const includesTopic = document.getElementById('includesTopicSwitch').checked;
            let roles = [];
            let topic = null;
            
            if (includesTopic && data.topic && Array.isArray(data.roles)) {
                // テーマと役割が含まれる形式: {"topic": "テーマ", "roles": [{name, description}, ...]}
                topic = data.topic;
                roles = data.roles.map(role => ({
                    name: role.name || '',
                    description: role.description || ''
                }));
            } else if (Array.isArray(data)) {
                // 役割のみの配列: [{name, description}, ...]
                roles = data.map(role => ({
                    name: role.name || '',
                    description: role.description || ''
                }));
            } else if (typeof data === 'object') {
                // その他のオブジェクト形式
                throw new Error('サポートされていないJSON形式です。説明に記載された形式に従ってください。');
            } else {
                throw new Error('無効なJSON形式です。説明に記載された形式に従ってください。');
            }
            
            // 空の役割名や説明がある場合は除外
            roles = roles.filter(role => role.name.trim() !== '');
            
            return { roles, topic };
        } catch (error) {
            // すべてのエラーをこのレベルで捕捉
            console.error("Error in parseRolesJson:", error);
            throw error; // エラーを呼び出し元に再スロー
        }
    }
    
    // CSV形式の役割ファイルをパースする
    function parseRolesCsv(content) {
        const includesTopic = document.getElementById('includesTopicSwitch').checked;
        const lines = content.split(/\r?\n/)
            .map(line => line.trim())
            .filter(line => line !== '');
            
        let roles = [];
        let topic = null;
        
        if (lines.length === 0) {
            throw new Error('CSVファイルが空です。');
        }
        
        if (includesTopic) {
            // 1行目をテーマとして解析
            const topicLine = lines[0].split(',');
            if (topicLine.length >= 2) {
                topic = topicLine[1].trim();
            } else {
                topic = topicLine[0].trim();
            }
            
            // 残りの行を役割として解析
            for (let i = 1; i < lines.length; i++) {
                const columns = lines[i].split(',');
                if (columns.length >= 2) {
                    roles.push({
                        name: columns[0].trim(),
                        description: columns[1].trim()
                    });
                }
            }
        } else {
            // すべての行を役割として解析
            for (let i = 0; i < lines.length; i++) {
                const columns = lines[i].split(',');
                if (columns.length >= 2) {
                    roles.push({
                        name: columns[0].trim(),
                        description: columns[1].trim()
                    });
                }
            }
        }
        
        // 空の役割名がある場合は除外
        roles = roles.filter(role => role.name !== '');
        
        return { roles, topic };
    }
    
    // テキスト形式の役割ファイルをパースする
    function parseRolesTxt(content) {
        const includesTopic = document.getElementById('includesTopicSwitch').checked;
        const lines = content.split(/\r?\n/)
            .map(line => line.trim())
            .filter(line => line !== '');
            
        let roles = [];
        let topic = null;
        
        if (lines.length === 0) {
            throw new Error('テキストファイルが空です。');
        }
        
        if (includesTopic) {
            // 1行目をテーマとして解析
            const topicParts = lines[0].split(':');
            if (topicParts.length >= 2) {
                topic = topicParts[1].trim();
            } else {
                topic = topicParts[0].trim();
            }
            
            // 残りの行を役割として解析
            for (let i = 1; i < lines.length; i++) {
                const parts = lines[i].split(':');
                if (parts.length >= 2) {
                    roles.push({
                        name: parts[0].trim(),
                        description: parts[1].trim()
                    });
                }
            }
        } else {
            // すべての行を役割として解析
            for (let i = 0; i < lines.length; i++) {
                const parts = lines[i].split(':');
                if (parts.length >= 2) {
                    roles.push({
                        name: parts[0].trim(),
                        description: parts[1].trim()
                    });
                }
            }
        }
        
        // 空の役割名がある場合は除外
        roles = roles.filter(role => role.name !== '');
        
        return { roles, topic };
    }
    
    // 役割のプレビューを表示
    function displayRolesPreview(result) {
        // プレビューコンテナをクリア
        rolesPreviewContainer.innerHTML = '';
        
        const roles = result.roles;
        const topic = result.topic;
        
        // テーマが存在する場合は表示
        if (topic) {
            const topicHeader = document.createElement('div');
            topicHeader.className = 'alert alert-info mb-2 py-2';
            topicHeader.innerHTML = `<strong>テーマ:</strong> ${escapeHtml(topic)}`;
            rolesPreviewContainer.appendChild(topicHeader);
        }
        
        // 役割のリストを表示
        const list = document.createElement('ul');
        list.className = 'list-group list-group-flush';
        
        roles.forEach((role, index) => {
            const item = document.createElement('li');
            item.className = 'list-group-item bg-transparent';
            item.innerHTML = `<small>${index + 1}.</small> <strong>${escapeHtml(role.name)}</strong>: ${escapeHtml(role.description)}`;
            
            // データ属性に役割の詳細を保存
            item.dataset.roleName = role.name;
            item.dataset.roleDescription = role.description;
            
            list.appendChild(item);
        });
        
        rolesPreviewContainer.appendChild(list);
        
        // 役割の数を表示
        const countInfo = document.createElement('div');
        countInfo.className = 'text-end text-muted mt-2 small';
        countInfo.textContent = `合計 ${roles.length} 個の役割`;
        rolesPreviewContainer.appendChild(countInfo);
    }
    
    // 役割をフォームにインポート
    function importRoles() {
        try {
            // プレビューから役割とテーマを取得
            const roleListItems = rolesPreviewContainer.querySelectorAll('li');
            const roles = Array.from(roleListItems).map(li => {
                // データ属性から役割情報を取得
                return {
                    name: li.dataset.roleName,
                    description: li.dataset.roleDescription
                };
            }).filter(role => role.name && role.description);  // 有効な役割のみをフィルタリング
            
            // テーマの取得を試みる
            const topicElement = rolesPreviewContainer.querySelector('.alert-info');
            let topic = null;
            if (topicElement) {
                // "テーマ:" の後のテキストを抽出
                const topicText = topicElement.innerText;
                const match = topicText.match(/テーマ:\s*(.*)/);
                if (match && match[1]) {
                    topic = match[1].trim();
                }
            }
            
            // 役割が見つからない場合はエラー
            if (roles.length === 0) {
                throw new Error('インポートする役割が見つかりません。');
            }
            
            // テーマが見つかった場合は設定
            if (topic) {
                topicInput.value = topic;
            }
            
            // 既存の役割をクリアするかどうか
            if (clearExistingRolesCheckbox.checked) {
                // 最初の2つの役割入力フィールドを残し、それ以外を削除
                const roleInputs = document.querySelectorAll('.role-input-group');
                for (let i = 2; i < roleInputs.length; i++) {
                    roleInputs[i].remove();
                }
                
                // 残った2つの入力フィールドをクリア
                document.querySelectorAll('.role-input').forEach(input => {
                    input.value = '';
                });
            }
            
            // 現在のフォーム内の役割入力フィールドを取得
            let roleInputs = document.querySelectorAll('.role-input');
            let currentIndex = 0;
            
            // 役割を入力フィールドに設定
            for (let i = 0; i < roles.length; i++) {
                const roleText = `${roles[i].name}: ${roles[i].description}`;
                if (currentIndex < roleInputs.length) {
                    // 既存の入力フィールドを使用
                    roleInputs[currentIndex].value = roleText;
                    currentIndex++;
                } else {
                    // 新しい入力フィールドを追加
                    addRoleInput(roleText);
                }
            }
            
            // 成功メッセージを表示
            let successMessage = `${roles.length}個の役割が正常にインポートされました。`;
            if (topic) {
                successMessage += ` テーマ「${topic}」も設定されました。`;
            }
            rolesUploadStatusMessage.textContent = successMessage;
            rolesUploadStatus.classList.remove('d-none');
            
            // モーダルを閉じる（少し遅延させて成功メッセージを見せる）
            setTimeout(() => {
                uploadRolesModal.hide();
                
                // 入力フィールドの削除ボタンの状態を更新
                updateRemoveButtons();
            }, 1500);
            
        } catch (error) {
            // エラー処理
            rolesUploadErrorMessage.textContent = error.message;
            rolesUploadError.classList.remove('d-none');
            console.error('Error importing roles:', error);
        }
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
        
        // システムメッセージを含める
        const systemMessages = discussionContainer.querySelectorAll('.system-message');
        systemMessages.forEach(msg => {
            const content = msg.querySelector('.system-content').textContent;
            text += `【システムメッセージ】\n${content}\n\n`;
        });
        
        // コンサルタント分析を含める
        const consultantMessages = discussionContainer.querySelectorAll('.consultant-message');
        consultantMessages.forEach(msg => {
            const content = msg.querySelector('.consultant-content').textContent;
            text += `【コンサルタント分析】\n${content}\n\n`;
        });
        
        // 通常の会話バブル
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
        if (!['pdf', 'txt', 'docx', 'xlsx'].includes(fileExt)) {
            showDocumentError('サポートされていないファイル形式です。PDF, TXT, DOCX, XLSXのいずれかを選択してください。');
            return;
        }
        
        // アップロードボタンの状態を変更
        const uploadBtn = document.getElementById('uploadDocumentBtn');
        const originalText = uploadBtn.innerHTML;
        uploadBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> アップロード中...';
        uploadBtn.disabled = true;
        
        // エラー表示をクリア
        hideDocumentError();
        
        // まずセッションをクリアしてから、ファイルをアップロード
        console.log("Clearing document before upload");
        
        // セッションデータをクリア
        sessionStorage.removeItem('uploadedDocument');
        localStorage.removeItem('documentAnalysisData');
        
        // ドキュメント分析結果をクリア
        const analysisContainer = document.getElementById('documentAnalysisContainer');
        if (analysisContainer) {
            analysisContainer.innerHTML = '';
        }
        
        // サーバー側のセッションもクリア
        fetch('/clear-document', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(() => {
            console.log("Session cleared, now uploading file");
            
            // クリア後にアップロード処理
            // FormDataの作成
            const formData = new FormData();
            formData.append('file', file);
            
            // ファイルアップロード
            return fetch('/upload-document', {
                method: 'POST',
                body: formData
            });
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
                console.log("Document upload successful:", data);
                
                // セッションに保存
                sessionStorage.setItem('uploadedDocument', JSON.stringify({
                    name: file.name,
                    type: file.type,
                    timestamp: new Date().getTime() // タイムスタンプを追加
                }));
                
                showDocumentSuccess(file.name);
                updateDocumentInfo(file.name);
                
                // 分析結果があれば表示（成功メッセージに追加情報を表示）
                if (data.has_analysis) {
                    document.getElementById('documentSuccessMessage').innerHTML += '<br><small class="text-success mt-1"><i class="bi bi-check-circle"></i> 文書分析が完了しました。詳細情報が利用可能です。</small>';
                    // 分析結果を取得して表示
                    setTimeout(() => {
                        fetchDocumentAnalysis();
                    }, 500);
                }
                
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
        // ID付きで参照できるように
        documentUploadStatus.innerHTML = `<div id="documentSuccessMessage" class="mb-0">ファイル <strong>${fileName}</strong> が正常にアップロードされました。</div>`;
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
        
        // 文書分析情報を取得して表示
        fetchDocumentAnalysis();
    }
    
    function fetchDocumentAnalysis() {
        fetch('/get-document-analysis', {
            method: 'GET'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayDocumentAnalysis(data.analysis, data.rag_data, data.document_name);
            } else {
                console.log("No document analysis available:", data.error);
            }
        })
        .catch(error => {
            console.error("Error fetching document analysis:", error);
        });
    }
    
    function displayDocumentAnalysis(analysis, ragData, fileName) {
        // 分析結果表示用のコンテナを取得または作成
        let analysisContainer = document.getElementById('documentAnalysisContainer');
        if (!analysisContainer) {
            analysisContainer = document.createElement('div');
            analysisContainer.id = 'documentAnalysisContainer';
            analysisContainer.className = 'mt-3 mb-4';
            
            // 文書情報の後に挿入
            const documentInfoSection = document.getElementById('documentInfo');
            documentInfoSection.parentNode.insertBefore(analysisContainer, documentInfoSection.nextSibling);
        }
        
        // 分析結果がなければ何もしない
        if (!analysis) {
            analysisContainer.innerHTML = '';
            return;
        }
        
        // 分析結果を表示
        let analysisContent = `
        <div class="card border-info">
            <div class="card-header bg-info bg-opacity-25">
                <h5 class="mb-0">
                    <i class="bi bi-search"></i> 文書分析結果
                    <button class="btn btn-sm btn-outline-primary float-end" type="button" data-bs-toggle="collapse" 
                            data-bs-target="#analysisCollapse" aria-expanded="false" aria-controls="analysisCollapse">
                        詳細表示
                    </button>
                </h5>
            </div>
            <div class="card-body">
                <p class="analysis-summary mb-2">
                    <strong>要約:</strong> ${analysis.summary || '要約なし'}
                </p>
                
                <div class="collapse" id="analysisCollapse">
                    <div class="card card-body mt-2 mb-3" style="background-color: #000; color: var(--bs-light);">
                        <div class="row">
                            <div class="col-md-6">
                                <h6><i class="bi bi-file-earmark-text"></i> 文書メタデータ</h6>
                                <ul class="list-unstyled">
                                    <li><small>ファイル名: ${fileName}</small></li>
                                    <li><small>文書タイプ: ${analysis.metadata?.document_type || '不明'}</small></li>
                                    <li><small>推定タイトル: ${analysis.metadata?.estimated_title || '不明'}</small></li>
                                    <li><small>日付: ${analysis.metadata?.possible_date || '記載なし'}</small></li>
                                </ul>
                            </div>
                            <div class="col-md-6">
                                <h6><i class="bi bi-layout-text-window"></i> 文書構造</h6>
                                <ul class="list-unstyled">
                                    <li><small>段落数: ${analysis.structure?.paragraph_count || 0}</small></li>
                                    <li><small>セクション数: ${analysis.structure?.sections_count || 0}</small></li>
                                </ul>
                            </div>
                        </div>
                        
                        <div class="mt-3">
                            <h6><i class="bi bi-tags"></i> 重要キーワード</h6>
                            <div>
        `;
        
        // キーワードを表示（ある場合）
        if (analysis.structure?.key_terms && analysis.structure.key_terms.length > 0) {
            analysis.structure.key_terms.forEach(term => {
                analysisContent += `<span class="badge bg-info text-light me-1 mb-1">${term}</span>`;
            });
        } else if (ragData?.search_keywords && ragData.search_keywords.length > 0) {
            ragData.search_keywords.forEach(keyword => {
                analysisContent += `<span class="badge bg-info text-light me-1 mb-1">${keyword}</span>`;
            });
        } else {
            analysisContent += `<p class="small text-muted">重要キーワードがありません</p>`;
        }
        
        analysisContent += `
                            </div>
                        </div>
                        
                        <div class="mt-3">
                            <h6><i class="bi bi-lightbulb"></i> 重要概念</h6>
                            <div>
        `;
        
        // 重要概念を表示（ある場合）
        if (ragData?.key_concepts && ragData.key_concepts.length > 0) {
            ragData.key_concepts.forEach(concept => {
                const conceptName = typeof concept === 'object' ? concept.name : concept;
                analysisContent += `<div class="badge bg-success text-light me-1 mb-1">${conceptName}</div>`;
            });
        } else {
            analysisContent += `<p class="small text-muted">重要概念がありません</p>`;
        }
        
        analysisContent += `
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `;
        
        analysisContainer.innerHTML = analysisContent;
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
            // UI表示をリセット
            document.getElementById('documentName').textContent = 'ファイルアップロード待ち';
            hideDocumentSuccess();
            
            // ドキュメント分析結果をクリア
            const analysisContainer = document.getElementById('documentAnalysisContainer');
            if (analysisContainer) {
                analysisContainer.innerHTML = '';
            }
            
            // ドキュメントを使用したディスカッション生成を無効化
            generateWithDocBtn.disabled = true;
            
            // 念のため、ローカルストレージからも関連データをクリア
            localStorage.removeItem('documentAnalysisData');
            
            // ページをリロードして完全にクリーンな状態にする
            if (confirm('文書データを完全にクリアするためにページをリロードしますか？')) {
                window.location.reload();
            }
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
        } else {
            // ファイルがアップロードされていない初期状態ではデフォルトメッセージを表示
            document.getElementById('documentName').textContent = 'ファイルアップロード待ち';
            generateWithDocBtn.disabled = true;
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
        
        // セッションステータスをコンソールに表示（デバッグ用）
        console.log("Document session data:", sessionStorage.getItem('uploadedDocument'));
        
        // サーバーからドキュメントのステータスを確認
        fetch('/get-document-text', {
            method: 'GET'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.document_text) {
                console.log("Document verified, starting generation");
                // 生成処理の開始
                generateDiscussionWithDocument(topic, roles, numTurns);
            } else {
                // セッションステータスをクライアント側でリセットする
                sessionStorage.removeItem('uploadedDocument');
                showError('有効なドキュメントがアップロードされていません。先にドキュメントをアップロードしてください。');
                
                // ドキュメントステータス表示をリセット
                document.getElementById('documentName').textContent = 'ファイルアップロード待ち';
                generateWithDocBtn.disabled = true;
                
                console.error("Server could not find the document, session is invalid");
            }
        })
        .catch(error => {
            console.error("Error verifying document:", error);
            showError('ドキュメントの確認中にエラーが発生しました。再度ドキュメントをアップロードしてください。');
            
            // エラー時にもセッションをクリア
            sessionStorage.removeItem('uploadedDocument');
        });
    }
    
    function generateDiscussionWithDocument(topic, roles, numTurns) {
        // Show loading indicator
        showLoading(true);
        hideError();
        
        // Get selected language
        const language = document.getElementById('language').value;
        
        // デバッグ情報をログに記録
        console.log(`Starting discussion with document: topic=${topic}, roles=${roles.length}, numTurns=${numTurns}, language=${language}`);
        
        // ボタンを無効化
        exportTextBtn.disabled = true;
        copyTextBtn.disabled = true;
        generateActionItemsBtn.disabled = true;
        summarizeDiscussionBtn.disabled = true;
        continueDiscussionBtn.disabled = true;
        provideGuidanceBtn.disabled = true;
        
        // 最初に文書が本当にアップロードされているか確認
        fetch('/get-document-text', {
            method: 'GET'
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success || !data.document_text) {
                throw new Error('ドキュメントが正しくアップロードされていないか、内容が空です。再アップロードしてください。');
            }
            
            console.log(`Document found, length: ${data.document_text.length} characters`);
            
            // 文書が確認できたので処理を続行
            // 状態を初期化
            currentDiscussion = [];
            let currentTurn = 0;
            let currentRoleIndex = 0;
            
            // ドキュメント参照を使用するフラグをセット
            const useDocument = true;
            
            console.log(`Starting discussion generation with document flag=${useDocument}`);
            
            // ターンごとに生成する処理
            generateNextTurnWithDocument(topic, roles, numTurns, currentDiscussion, currentTurn, currentRoleIndex, language, useDocument);
        })
        .catch(error => {
            showLoading(false);
            showError(error.message || 'ドキュメントの取得中にエラーが発生しました。');
            console.error('Error checking document:', error);
        });
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
            
            // ドキュメントの内容を表示
            fetch('/get-document-text', {
                method: 'GET'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success && data.document_text) {
                    const documentCard = document.createElement('div');
                    documentCard.className = 'document-display card mb-3 border-info';
                    documentCard.innerHTML = `
                        <div class="card-header bg-info bg-opacity-25">
                            <strong><i class="bi bi-file-text"></i> アップロードされた文書</strong>
                        </div>
                        <div class="card-body document-body">
                            <div class="document-content" style="max-height: 300px; overflow-y: auto; white-space: pre-wrap; font-size: 0.85rem;">${data.document_text}</div>
                        </div>
                    `;
                    discussionContainer.appendChild(documentCard);
                }
            })
            .catch(error => {
                console.error("文書内容の取得中にエラー:", error);
            });
        }
        
        // ロード表示を更新
        loadingIndicator.querySelector('.progress-bar').style.width = `${percent}%`;
        loadingIndicator.querySelector('.progress-bar').setAttribute('aria-valuenow', percent);
        loadingIndicator.querySelector('.progress-text').textContent = 
            `${roles[currentRoleIndex]}の発言を生成中... (文書参照) (${currentIteration}/${totalIterations})`;
        
        // 現在の設定を取得
        const currentSettings = getCurrentSettingsFromUI();
        
        // リクエストデータを準備
        const requestData = {
            topic: topic,
            roles: roles,
            numTurns: numTurns,
            discussion: discussion,
            currentTurn: currentTurn,
            currentRoleIndex: currentRoleIndex,
            language: language,
            use_document: useDocument,
            // モデル設定を追加
            model: currentSettings.model,
            temperature: currentSettings.temperature,
            maxOutputTokens: currentSettings.maxOutputTokens
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
        
        // コンサルタント分析を含める
        const consultantMessages = discussionContainer.querySelectorAll('.consultant-message');
        consultantMessages.forEach(msg => {
            const content = msg.querySelector('.consultant-content').textContent;
            discussionData.push({
                role: "コンサルタント",
                content: content
            });
        });
        
        // 通常のディスカッションバブル
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
        
        // コンサルタント分析を含める
        const consultantMessages = discussionContainer.querySelectorAll('.consultant-message');
        consultantMessages.forEach(msg => {
            const content = msg.querySelector('.consultant-content').textContent;
            discussionData.push({
                role: "コンサルタント",
                content: content
            });
        });
        
        // 通常のディスカッションバブル
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
        
        // コンサルタント分析を含める
        const consultantMessages = discussionContainer.querySelectorAll('.consultant-message');
        consultantMessages.forEach(msg => {
            const content = msg.querySelector('.consultant-content').textContent;
            discussionData.push({
                role: "コンサルタント",
                content: content
            });
        });
        
        // 通常のディスカッションバブル
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
        
        // 現在の設定を取得
        const currentSettings = getCurrentSettingsFromUI();
        
        // 初期リクエストデータ作成（ターンごとに更新される）
        let requestData = {
            discussion_data: discussionData,
            topic: topic,
            roles: roles,
            num_additional_turns: additionalTurns,
            language: language,
            use_document: useDocument,
            current_turn: 0,  // 初期ターン
            current_role_index: 0,  // 初期役割インデックス
            // モデル設定を追加
            model: currentSettings.model,
            temperature: currentSettings.temperature,
            maxOutputTokens: currentSettings.maxOutputTokens
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
        
        // コンサルタント分析を含める
        const consultantMessages = discussionContainer.querySelectorAll('.consultant-message');
        consultantMessages.forEach(msg => {
            const content = msg.querySelector('.consultant-content').textContent;
            discussionData.push({
                role: "コンサルタント",
                content: content
            });
        });
        
        // 通常のディスカッションバブル
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
        
        // 現在の設定を取得
        const currentSettings = getCurrentSettingsFromUI();
        
        // リクエストデータ作成
        const requestData = {
            discussion_data: discussionData,
            topic: topic,
            instruction: instruction,
            num_additional_turns: numAdditionalTurns,
            use_document: useDocument,
            language: language,
            // モデル設定を追加
            model: currentSettings.model,
            temperature: currentSettings.temperature,
            maxOutputTokens: currentSettings.maxOutputTokens
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
    
    // 詳細設定関連の機能
    
    // 設定の初期値
    const defaultSettings = {
        model: 'gemini-2.0-flash-lite',
        temperature: 0.7,
        maxOutputTokens: 1024,
        saveSettings: true
    };
    
    // ローカルストレージから設定を読み込む
    function loadSettings() {
        try {
            const savedSettings = localStorage.getItem('discussionGeneratorSettings');
            if (savedSettings) {
                return JSON.parse(savedSettings);
            }
        } catch (e) {
            console.error('設定の読み込み中にエラーが発生しました:', e);
        }
        return defaultSettings;
    }
    
    // 設定を保存する
    function saveSettings(settings) {
        try {
            if (settings.saveSettings) {
                localStorage.setItem('discussionGeneratorSettings', JSON.stringify(settings));
            } else {
                localStorage.removeItem('discussionGeneratorSettings');
            }
        } catch (e) {
            console.error('設定の保存中にエラーが発生しました:', e);
        }
    }
    
    // UIに設定を適用する
    function applySettingsToUI(settings) {
        modelSelect.value = settings.model;
        temperatureSlider.value = settings.temperature;
        temperatureValue.textContent = settings.temperature;
        maxOutputTokens.value = settings.maxOutputTokens;
        saveSettingsSwitch.checked = settings.saveSettings;
    }
    
    // 現在のUI設定を取得する
    function getCurrentSettingsFromUI() {
        return {
            model: modelSelect.value,
            temperature: parseFloat(temperatureSlider.value),
            maxOutputTokens: parseInt(maxOutputTokens.value),
            saveSettings: saveSettingsSwitch.checked
        };
    }
    
    // 設定初期化と設定変更イベントリスナー登録
    function initSettings() {
        // 設定の読み込みと適用
        const settings = loadSettings();
        applySettingsToUI(settings);
        
        // スライダー値変更時の表示更新
        temperatureSlider.addEventListener('input', function() {
            temperatureValue.textContent = this.value;
        });
        
        // 設定保存ボタンのイベントリスナー
        saveSettingsBtn.addEventListener('click', function() {
            const currentSettings = getCurrentSettingsFromUI();
            saveSettings(currentSettings);
            
            // モーダルを閉じる
            const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
            modal.hide();
            
            // 成功メッセージを表示
            const toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            toastContainer.innerHTML = `
                <div class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                    <div class="toast-header bg-success text-white">
                        <strong class="me-auto"><i class="bi bi-check-circle"></i> 設定を保存しました</strong>
                        <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="閉じる"></button>
                    </div>
                    <div class="toast-body">
                        生成AIモデルと温度設定が更新されました。
                    </div>
                </div>
            `;
            
            document.body.appendChild(toastContainer);
            const toastElement = toastContainer.querySelector('.toast');
            const toast = new bootstrap.Toast(toastElement);
            toast.show();
            
            // 少し経ったら要素を削除
            setTimeout(() => {
                if (toastContainer.parentNode) {
                    toastContainer.parentNode.removeChild(toastContainer);
                }
            }, 3000);
        });
    }
    
    // 設定の初期化を実行
    initSettings();
    
    // HTML特殊文字をエスケープする関数
    function escapeHtml(text) {
        if (text === undefined || text === null) return '';
        text = String(text);
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