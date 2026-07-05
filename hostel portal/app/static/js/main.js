document.addEventListener("DOMContentLoaded", () => {
    // 1. Setup Alert Auto-Dismissal
    const alerts = document.querySelectorAll(".alert");
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = "opacity 0.5s ease";
            alert.style.opacity = "0";
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // 2. Student Registration Flow: Room Manual Selection
    const registerForm = document.querySelector("#registration-form");
    if (registerForm) {
        const yearSelect = document.querySelector("#year-select");
        const roomNumberSelect = document.querySelector("#room-number-select");
        const suggestionText = document.querySelector("#allocation-suggestion-text");

        const generateRoomsForYear = (yearVal) => {
            let prefix = "1";
            if (yearVal === "2") {
                prefix = "2";
            } else if (yearVal === "3" || yearVal === "4") {
                prefix = "3";
            }
            
            const rooms = [];
            for (let i = 1; i <= 30; i++) {
                const suffix = i < 10 ? `0${i}` : `${i}`;
                rooms.push(`${prefix}${suffix}`);
            }
            return rooms;
        };

        const updateRoomList = () => {
            const yearVal = yearSelect.value;

            if (!yearVal) {
                if (suggestionText) {
                    suggestionText.textContent = "Please select your year of study to view available rooms.";
                    suggestionText.className = "stat-desc text-muted";
                }
                roomNumberSelect.innerHTML = '<option value="" disabled selected>Select Academic Year first</option>';
                roomNumberSelect.disabled = true;
                return;
            }

            // Generate room numbers locally
            const rooms = generateRoomsForYear(yearVal);
            
            // Clear existing options
            roomNumberSelect.innerHTML = "";
            
            // Default select room option
            const defaultRoomOpt = document.createElement("option");
            defaultRoomOpt.value = "";
            defaultRoomOpt.textContent = "Select Room Number";
            defaultRoomOpt.disabled = true;
            defaultRoomOpt.selected = true;
            roomNumberSelect.appendChild(defaultRoomOpt);

            rooms.forEach(room => {
                const opt = document.createElement("option");
                opt.value = room;
                opt.textContent = `Room ${room}`;
                roomNumberSelect.appendChild(opt);
            });
            roomNumberSelect.disabled = false;
            
            if (suggestionText) {
                suggestionText.textContent = "Select a room number to check its occupancy.";
                suggestionText.className = "stat-desc text-info fw-semibold";
            }
        };

        const checkRoomOccupancy = () => {
            const selectedRoomNumber = roomNumberSelect.value;

            if (!selectedRoomNumber) {
                return;
            }

            if (suggestionText) {
                suggestionText.textContent = `Checking vacancy for Room ${selectedRoomNumber}...`;
                suggestionText.className = "stat-desc text-primary";
            }

            fetch(`/api/room-occupancy?room_number=${selectedRoomNumber}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        const occupied = data.occupied_count;
                        const capacity = data.capacity;
                        const vacant = data.vacancy;
                        
                        if (vacant > 0) {
                            if (suggestionText) {
                                suggestionText.textContent = `${vacant} space(s) available in Room ${selectedRoomNumber} (Occupied: ${occupied}/${capacity}).`;
                                suggestionText.className = "stat-desc text-success fw-semibold";
                            }
                        } else {
                            if (suggestionText) {
                                suggestionText.textContent = `Room ${selectedRoomNumber} is fully occupied! Please choose another room.`;
                                suggestionText.className = "stat-desc text-danger fw-semibold";
                            }
                        }
                    } else {
                        if (suggestionText) {
                            suggestionText.textContent = `Room not initialized in system yet, it will be automatically created on submit.`;
                            suggestionText.className = "stat-desc text-success fw-semibold";
                        }
                    }
                })
                .catch(err => {
                    console.error("Failed to query room occupancy:", err);
                    if (suggestionText) {
                        suggestionText.textContent = "Error communicating with room occupancy service.";
                        suggestionText.className = "stat-desc text-danger";
                    }
                });
        };

        // Listen for change events
        yearSelect.addEventListener("change", updateRoomList);
        roomNumberSelect.addEventListener("change", checkRoomOccupancy);
        
        // Initial run if values are present
        if (yearSelect.value) {
            updateRoomList();
        }
    }

    // 3. AI Assistant Conversational Chat
    const chatBox = document.querySelector("#chat-box");
    if (chatBox) {
        const chatInput = document.querySelector("#chat-input");
        const chatSendBtn = document.querySelector("#chat-send-btn");
        const modeSelect = document.querySelector("#ai-mode-select");

        const appendMessage = (sender, text) => {
            const msgDiv = document.createElement("div");
            msgDiv.className = `message message-${sender}`;
            
            // Render markdown or paragraphs
            msgDiv.innerHTML = text.replace(/\n/g, "<br>");
            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        };

        const sendMessage = () => {
            const text = chatInput.value.trim();
            const mode = modeSelect ? modeSelect.value : "hostel_knowledge";
            
            if (!text) return;
            
            appendMessage("user", text);
            chatInput.value = "";
            
            // Create typing indicator
            const typingIndicator = document.createElement("div");
            typingIndicator.className = "message message-ai typing-indicator";
            typingIndicator.innerHTML = "Thinking...";
            chatBox.appendChild(typingIndicator);
            chatBox.scrollTop = chatBox.scrollHeight;
            
            fetch("/ai/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ message: text, mode: mode })
            })
            .then(res => res.json())
            .then(data => {
                typingIndicator.remove();
                if (data.success) {
                    appendMessage("ai", data.response);
                } else {
                    appendMessage("ai", `Error: ${data.response}`);
                }
            })
            .catch(err => {
                typingIndicator.remove();
                console.error("Failed to fetch chat response:", err);
                appendMessage("ai", "Communication error. Could not connect to AI service.");
            });
        };

        chatSendBtn.addEventListener("click", sendMessage);
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Quick help questions clicking
        const quickPrompts = document.querySelectorAll(".quick-prompt");
        quickPrompts.forEach(btn => {
            btn.addEventListener("click", () => {
                chatInput.value = btn.dataset.prompt;
                sendMessage();
            });
        });
    }

    // 4. Admin Floating Chatbot Toggle and Messaging
    const chatbotToggleBtn = document.querySelector("#chatbot-toggle-btn");
    const chatbotWindow = document.querySelector("#chatbot-window");
    const chatbotCloseBtn = document.querySelector("#chatbot-close-btn");
    const chatbotInput = document.querySelector("#chatbot-input");
    const chatbotSendBtn = document.querySelector("#chatbot-send-btn");
    const chatbotBody = document.querySelector("#chatbot-body");

    if (chatbotToggleBtn && chatbotWindow) {
        chatbotToggleBtn.addEventListener("click", () => {
            const isVisible = chatbotWindow.style.display !== "none";
            chatbotWindow.style.display = isVisible ? "none" : "flex";
            if (!isVisible) {
                chatbotInput.focus();
            }
        });

        chatbotCloseBtn.addEventListener("click", () => {
            chatbotWindow.style.display = "none";
        });

        const appendAdminChatMsg = (sender, text) => {
            const msgDiv = document.createElement("div");
            msgDiv.className = `chat-message ${sender}-message mb-3 p-2 rounded text-dark`;
            if (sender === "bot") {
                msgDiv.style.backgroundColor = "#f1f5f9";
                msgDiv.style.borderLeft = "3px solid #2563eb";
                msgDiv.style.fontSize = "0.85rem";
            } else {
                msgDiv.style.backgroundColor = "#dbeafe";
                msgDiv.style.borderLeft = "3px solid #3b82f6";
                msgDiv.style.alignSelf = "flex-end";
                msgDiv.style.fontSize = "0.85rem";
                msgDiv.style.marginLeft = "auto";
                msgDiv.style.width = "fit-content";
                msgDiv.style.maxWidth = "80%";
            }
            msgDiv.innerHTML = text.replace(/\n/g, "<br>");
            chatbotBody.appendChild(msgDiv);
            chatbotBody.scrollTop = chatbotBody.scrollHeight;
        };

        const sendAdminMessage = () => {
            const text = chatbotInput.value.trim();
            if (!text) return;

            appendAdminChatMsg("user", text);
            chatbotInput.value = "";

            const typing = document.createElement("div");
            typing.className = "chat-message bot-message mb-3 p-2 bg-light rounded text-muted";
            typing.style.fontSize = "0.8rem";
            typing.textContent = "Thinking...";
            chatbotBody.appendChild(typing);
            chatbotBody.scrollTop = chatbotBody.scrollHeight;

            fetch("/ai/admin_chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            })
            .then(res => res.json())
            .then(data => {
                typing.remove();
                if (data.success) {
                    appendAdminChatMsg("bot", data.response);
                } else {
                    appendAdminChatMsg("bot", `Error: ${data.response}`);
                }
            })
            .catch(err => {
                typing.remove();
                console.error("Chat error:", err);
                appendAdminChatMsg("bot", "Error connecting to server database chatbot.");
            });
        };

        chatbotSendBtn.addEventListener("click", sendAdminMessage);
        chatbotInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendAdminMessage();
            }
        });
    }

    // 5. Universal AI Explainer
    const explainBtn = document.querySelector("#ai-explain-btn");
    if (explainBtn) {
        explainBtn.addEventListener("click", () => {
            const modalEl = document.getElementById("aiExplainModal");
            const modal = new bootstrap.Modal(modalEl);
            modal.show();

            const loadingEl = document.getElementById("ai-explain-loading");
            const contentEl = document.getElementById("ai-explain-content");

            loadingEl.style.display = "block";
            contentEl.style.display = "none";
            contentEl.innerHTML = "";

            // Collect page content context
            const mainBody = document.querySelector(".content-body");
            const pageText = mainBody ? mainBody.innerText : document.body.innerText;

            fetch("/ai/explain_page", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    path: window.location.pathname,
                    title: document.title,
                    content: pageText.slice(0, 4000)
                })
            })
            .then(res => res.json())
            .then(data => {
                loadingEl.style.display = "none";
                contentEl.style.display = "block";
                if (data.success) {
                    contentEl.innerHTML = parseMarkdown(data.response);
                } else {
                    contentEl.innerHTML = `<div class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> Failed to explain page: ${data.response}</div>`;
                }
            })
            .catch(err => {
                loadingEl.style.display = "none";
                contentEl.style.display = "block";
                console.error("Explainer error:", err);
                contentEl.innerHTML = '<div class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> Connection failed to explainer service.</div>';
            });
        });
    }

    function parseMarkdown(text) {
        if (!text) return "";
        let html = text;
        
        // Escape HTML
        html = html
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
            
        // Headers
        html = html.replace(/^### (.*?)$/gm, '<h5 class="fw-bold mt-3 mb-2 text-dark">$1</h5>');
        html = html.replace(/^## (.*?)$/gm, '<h4 class="fw-bold mt-4 mb-2 text-primary border-bottom pb-1">$1</h4>');
        html = html.replace(/^# (.*?)$/gm, '<h3 class="fw-bold mt-4 mb-3 text-primary border-bottom pb-2">$1</h3>');
        
        // Bold / Italics
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Bullets
        html = html.replace(/^\s*-\s+(.*?)$/gm, '<li class="ms-3">$1</li>');
        html = html.replace(/^\s*\*\s+(.*?)$/gm, '<li class="ms-3">$1</li>');
        
        // Code
        html = html.replace(/`([^`]+)`/g, '<code class="bg-light px-1 py-0.5 rounded text-danger">$1</code>');
        
        // Newlines
        html = html.replace(/\n/g, '<br>');
        
        return html;
    }
});
