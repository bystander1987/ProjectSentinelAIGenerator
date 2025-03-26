document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const discussionForm = document.getElementById('discussionForm');
    const topicInput = document.getElementById('topic');
    const numTurnsInput = document.getElementById('numTurns');
    const rolesContainer = document.getElementById('rolesContainer');
    const addRoleBtn = document.getElementById('addRoleBtn');
    const generateBtn = document.getElementById('generateBtn');
    const discussionContainer = document.getElementById('discussionContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorDisplay = document.getElementById('errorDisplay');
    const errorMessage = document.getElementById('errorMessage');
    const discussionTopicHeader = document.getElementById('discussionTopicHeader');
    const exportTextBtn = document.getElementById('exportText');
    const copyTextBtn = document.getElementById('copyText');
    const exampleTopics = document.querySelectorAll('.example-topic');

    // Initialize the page
    initPage();

    function initPage() {
        // Event listeners
        discussionForm.addEventListener('submit', handleFormSubmit);
        addRoleBtn.addEventListener('click', addRoleInput);
        exportTextBtn.addEventListener('click', exportDiscussion);
        copyTextBtn.addEventListener('click', copyDiscussion);
        
        // Example topics
        exampleTopics.forEach(example => {
            example.addEventListener('click', loadExampleTopic);
        });

        // Enable removal buttons if there are more than 2 roles
        updateRemoveButtons();
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
        
        // Send request to server
        fetch('/generate-discussion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
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
            showLoading(false);
            showError(`エラー: ${error.message}`);
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
            discussionContainer.innerHTML = '';
            generateBtn.disabled = true;
        } else {
            loadingIndicator.classList.add('d-none');
            generateBtn.disabled = false;
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
        const topic = discussionTopicHeader.textContent.replace('Discussion: ', '');
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
});
