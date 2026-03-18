const API_URL = "http://localhost:8000/ask";

document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const sendBtn = document.getElementById("send-btn");

    // Prevent default form submission and handle it via JS
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const query = userInput.value.trim();
        if (!query) return;

        // 1. Add user message to UI
        appendMessage("user-message", query);
        userInput.value = "";
        
        // Disable input while thinking
        userInput.disabled = true;
        sendBtn.disabled = true;

        // 2. Add loading indicator
        const loadingId = appendLoadingIndicator();

        try {
            // 3. Make API call to FastAPI backend
            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Server error occurred");
            }

            const data = await response.json();
            
            // 4. Remove loading indicator and show AI response
            removeElement(loadingId);
            appendAIMessage(data);

        } catch (error) {
            removeElement(loadingId);
            appendMessage("ai-message", `⚠️ Error: ${error.message}. Please make sure the Python server is running.`);
        } finally {
            // Re-enable input
            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();
        }
    });

    function appendMessage(className, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${className}`;
        msgDiv.innerHTML = `<div class="message-bubble">${escapeHTML(text)}</div>`;
        chatBox.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv;
    }

    function appendLoadingIndicator() {
        const id = "loading-" + Date.now();
        const msgDiv = document.createElement("div");
        msgDiv.className = "message ai-message";
        msgDiv.id = id;
        msgDiv.innerHTML = `
            <div class="typing-indicator">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
        `;
        chatBox.appendChild(msgDiv);
        scrollToBottom();
        return id;
    }

    function removeElement(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function appendAIMessage(data) {
        const msgDiv = document.createElement("div");
        msgDiv.className = "message ai-message";
        
        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        
        // 1. Set the friendly text response
        let contentHTML = `<p>${escapeHTML(data.final_answer.message)}</p>`;
        
        // 2. Append formatted products if any exist
        const products = data.final_answer.products || [];
        if (products.length > 0) {
            contentHTML += `<div class="product-list">`;
            products.forEach(p => {
                const statusClass = p.stock > 0 ? 'in-stock' : 'out-of-stock';
                const statusText = p.stock > 0 ? `${p.stock} in stock` : 'Out of Stock';
                const priceText = p.price > 0 ? `$${parseFloat(p.price).toFixed(2)}` : 'N/A';
                
                contentHTML += `
                    <div class="product-card">
                        <div style="display:flex; flex-direction:column; gap:2px;">
                            <span class="product-name">${escapeHTML(p.name)}</span>
                            <span class="product-price">${priceText}</span>
                        </div>
                        <span class="status-badge ${statusClass}">${statusText}</span>
                    </div>
                `;
            });
            contentHTML += `</div>`;
        }

        // Add execution time (Optional detail)
        contentHTML += `<div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 8px; text-align: right;">
            ⚡ ${data.execution_time_seconds}s
        </div>`;

        bubble.innerHTML = contentHTML;
        msgDiv.appendChild(bubble);
        chatBox.appendChild(msgDiv);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function escapeHTML(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;")
            .replace(/\n/g, "<br>");
    }
});
