// Predefined issue categories for @super mention
const SUPER_CATEGORIES = [
    { id: 'financial_unlock', label: 'Financial Unblock / Correction', icon: 'currency-rupee' },
    { id: 'update_dates', label: 'Update Dates / Schedule', icon: 'calendar' },
    { id: 'update_trainer', label: 'Update Trainer Mapping', icon: 'chalkboard-teacher' },
    { id: 'system_bug', label: 'System Bug Report', icon: 'bug' },
    { id: 'new_feature', label: 'New Feature Request', icon: 'lightbulb' },
    { id: 'crm_correction', label: 'CRM Data Correction', icon: 'database' },
    { id: 'other', label: 'Other', icon: 'dots-three' }
];

/**
 * Setup @super mention autocomplete detector for a textarea
 * @param {string} textareaId - ID of the textarea element
 * @param {string} contextType - Type of context (e.g., 'inquiry', 'program')
 * @param {number} contextId - ID of the context entity
 */
function setupSuperMentionDetector(textareaId, contextType, contextId) {
    const textarea = document.getElementById(textareaId);
    if (!textarea) {
        console.error(`Textarea with id "${textareaId}" not found`);
        return;
    }

    const dropdown = createCategoryDropdown();

    // Position dropdown near textarea
    textarea.parentElement.style.position = 'relative';
    textarea.parentElement.appendChild(dropdown);

    let selectedCategory = null;

    // Detect @super typing
    textarea.addEventListener('input', function (e) {
        const text = this.value;
        const cursorPos = this.selectionStart;

        // Check if @super was just typed
        const beforeCursor = text.substring(0, cursorPos);
        const mentionMatch = beforeCursor.match(/@super\s*$/i);

        if (mentionMatch) {
            // Show dropdown
            showDropdown(dropdown, this);
        } else {
            // Hide dropdown if not typing @super
            if (!beforeCursor.match(/@super\s+\[/i)) {
                dropdown.style.display = 'none';
            }
        }
    });

    // Handle category selection
    dropdown.addEventListener('click', function (e) {
        const categoryItem = e.target.closest('[data-category-id]');
        if (categoryItem) {
            const categoryId = categoryItem.dataset.categoryId;
            const category = SUPER_CATEGORIES.find(c => c.id === categoryId);

            selectedCategory = category;

            // Replace @super with selected category
            const text = textarea.value;
            const newText = text.replace(/@super\s*$/i, `@super [${category.label}] `);
            textarea.value = newText;

            // Hide dropdown
            dropdown.style.display = 'none';
            textarea.focus();

            // Store selected category for submission
            textarea.dataset.superCategory = categoryId;
        }
    });
}

function createCategoryDropdown() {
    const dropdown = document.createElement('div');
    dropdown.className = 'super-mention-dropdown';
    dropdown.style.cssText = `
        display: none;
        position: absolute;
        bottom: 100%;
        left: 0;
        background: var(--bg-surface);
        border: 1px solid var(--border-light);
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        max-width: 350px;
        min-width: 300px;
        z-index: 1000;
        margin-bottom: 8px;
    `;

    // Header
    const header = document.createElement('div');
    header.style.cssText = `
        padding: 12px 16px;
        border-bottom: 1px solid var(--border-light);
        font-weight: 600;
        font-size: 0.75rem;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    `;
    header.textContent = 'Select Category';
    dropdown.appendChild(header);

    // Category items
    SUPER_CATEGORIES.forEach(category => {
        const item = document.createElement('div');
        item.dataset.categoryId = category.id;
        item.style.cssText = `
            padding: 12px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: background 0.2s;
            font-size: 0.875rem;
        `;
        item.innerHTML = `
            <i class="ph ph-${category.icon}" style="font-size: 1.2rem; color: var(--primary);"></i>
            <span style="color: var(--text-primary);">${category.label}</span>
        `;

        item.addEventListener('mouseenter', () => {
            item.style.background = 'var(--bg-hover, #f3f4f6)';
        });
        item.addEventListener('mouseleave', () => {
            item.style.background = 'transparent';
        });

        dropdown.appendChild(item);
    });

    return dropdown;
}

function showDropdown(dropdown, textarea) {
    dropdown.style.display = 'block';

    // Position dropdown above textarea
    const rect = textarea.getBoundingClientRect();
    const parent = textarea.parentElement.getBoundingClientRect();

    // Calculate position relative to parent
    dropdown.style.bottom = `${textarea.offsetHeight + 8}px`;
}

/**
 * Handle @super mention submission
 * @param {HTMLElement} textarea - The textarea element
 * @param {string} contextType - Type of context
 * @param {number} contextId - ID of the context
 * @returns {Promise<boolean>} - True if handled, false otherwise
 */
async function handleSuperMentionSubmit(textarea, contextType, contextId) {
    const text = textarea.value;

    // Check if @super mention exists
    if (!text.includes('@super')) {
        return false;
    }

    const categoryId = textarea.dataset.superCategory;

    if (!categoryId) {
        alert('Please select a category from the dropdown when using @super');
        return true; // Prevent normal submission
    }

    // Extract description after category
    const descMatch = text.match(/@super\s*\[.+?\]\s*(.+)/is);
    const description = descMatch ? descMatch[1].trim() : '';

    if (!description) {
        alert('Please provide a description after selecting the category');
        return true; // Prevent normal submission
    }

    try {
        const response = await fetch('/api/super-mention', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
            },
            body: JSON.stringify({
                category_id: categoryId,
                description: description,
                context_type: contextType,
                context_id: contextId
            })
        });

        const data = await response.json();

        if (data.is_super_admin) {
            // Show ticket creation dialog for super admin
            if (data.show_dialog) {
                openTicketDialog(categoryId, description, contextType, contextId);
            }
        } else {
            // Show success and redirect for regular users
            showSuccessMessage('Support ticket created and assigned to Super Admin!');
            setTimeout(() => {
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    location.reload();
                }
            }, 1500);
        }

        return true; // Handled
    } catch (error) {
        console.error('Error submitting @super mention:', error);
        alert('Error creating support ticket. Please try again.');
        return true; // Prevent normal submission
    }
}

function showSuccessMessage(message) {
    // Check if flash message container exists
    const flashContainer = document.querySelector('.flash-messages');
    if (flashContainer) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flash success';
        messageDiv.textContent = message;
        flashContainer.appendChild(messageDiv);

        setTimeout(() => {
            messageDiv.remove();
        }, 3000);
    } else {
        // Fallback to alert
        alert(message);
    }
}

function openTicketDialog(categoryId, description, contextType, contextId) {
    // For super admin, show a confirm dialog (simple version for now)
    const category = SUPER_CATEGORIES.find(c => c.id === categoryId);
    const confirmMessage = `Create support ticket?\n\nCategory: ${category.label}\nDescription: ${description}\n\nThis will create a ticket assigned to you.`;

    if (confirm(confirmMessage)) {
        // Create the ticket
        fetch('/api/super-mention/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
            },
            body: JSON.stringify({
                category_id: categoryId,
                description: description,
                context_type: contextType,
                context_id: contextId
            })
        }).then(response => response.json())
            .then(data => {
                if (data.ticket_id) {
                    showSuccessMessage('Ticket created successfully!');
                    setTimeout(() => {
                        if (data.redirect_url) {
                            window.location.href = data.redirect_url;
                        } else {
                            location.reload();
                        }
                    }, 1500);
                }
            })
            .catch(error => {
                console.error('Error creating ticket:', error);
                alert('Error creating ticket. Please try again.');
            });
    }
}
