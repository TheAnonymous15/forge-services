 // Glassmorphic 3D Waitlist Modal Functionality
(function() {
    'use strict';

    const modal = document.getElementById('waitlist-modal');
    const modalContent = document.getElementById('modal-content');
    const modalForm = document.getElementById('modal-waitlist-form');
    const modalSuccessMessage = document.getElementById('modal-success-message');
    const modalSubmitBtn = document.getElementById('modal-submit-btn');
    const modalBtnText = document.getElementById('modal-btn-text');

    // ── Third column helpers ────────────────────────
    function col3Update() {
        const col3      = document.getElementById('modal-col-3');
        const grid      = document.getElementById('modal-grid');
        const div23     = document.getElementById('divider-23');
        const empty     = document.getElementById('col3-empty');
        const skillWrap = document.getElementById('col3-skills-wrap');
        const fieldWrap = document.getElementById('col3-fields-wrap');
        const skillList = document.getElementById('col3-skills');
        const fieldList = document.getElementById('col3-fields');
        if (!col3 || !grid) return;

        const hasSkills = skillList && skillList.children.length > 0;
        const hasFields = fieldList && fieldList.children.length > 0;
        const hasAny    = hasSkills || hasFields;

        // Use inline styles — Tailwind CDN won't have grid-cols-3 pre-built
        if (hasAny) {
            col3.style.display  = 'block';
            grid.style.gridTemplateColumns = 'repeat(3, minmax(0, 1fr))';
            if (div23) div23.style.display = 'block';
        } else {
            col3.style.display  = 'none';
            grid.style.gridTemplateColumns = 'repeat(2, minmax(0, 1fr))';
            if (div23) div23.style.display = 'none';
        }

        if (skillWrap) skillWrap.style.display = hasSkills ? 'block' : 'none';
        if (fieldWrap) fieldWrap.style.display = hasFields ? 'block' : 'none';
        if (empty)     empty.style.display     = hasAny    ? 'none'  : 'block';
    }

    function col3AddTag(listId, val, label, accentColor, onRemove) {
        const list = document.getElementById(listId);
        if (!list) return;
        const tag = document.createElement('div');
        tag.id = 'col3-tag-' + listId + '-' + val.replace(/\s+/g,'_');
        tag.className = 'flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all duration-150';
        tag.style.cssText = `background:${accentColor}22;border:1px solid ${accentColor}55;color:${accentColor};`;
        tag.innerHTML = `
            <span class="col3-tag-label leading-none truncate">${label}</span>
            <button type="button" class="flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center opacity-60 hover:opacity-100 transition-opacity" style="background:${accentColor}33;" data-remove="${val}">
                <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>`;
        tag.querySelector('[data-remove]').addEventListener('click', () => onRemove(val));
        list.appendChild(tag);
        col3Update();
    }

    function col3RemoveTag(listId, val) {
        const tag = document.getElementById('col3-tag-' + listId + '-' + val.replace(/\s+/g,'_'));
        if (tag) tag.remove();
        col3Update();
    }

    // ── Opportunity type pill toggle ────────────────
    function initOppPills() {
        document.querySelectorAll('.opp-pill').forEach(div => {
            const input = div.previousElementSibling;
            if (!input) return;
            const activeClass = 'opp-active-' + input.value;

            div.addEventListener('click', () => {
                input.checked = !input.checked;
                if (input.checked) {
                    div.classList.add(activeClass);
                } else {
                    div.classList.remove(activeClass);
                }
            });
        });
    }

    // ── Skill / Field pill toggle ───────────────────
    function initPills(selector, hiddenContainerId, inputName, activeClass, counterId, col3ListId, accentColor, otherWrapId, otherInputId) {
        const pills      = document.querySelectorAll(selector);
        const container  = document.getElementById(hiddenContainerId);
        const counter    = counterId    ? document.getElementById(counterId)    : null;
        const otherWrap  = otherWrapId  ? document.getElementById(otherWrapId)  : null;
        const otherInput = otherInputId ? document.getElementById(otherInputId) : null;
        if (!pills.length || !container) return;

        function updateCounter() {
            if (!counter) return;
            const n = container.querySelectorAll('input').length;
            counter.textContent = n + ' selected';
            counter.style.display = n > 0 ? 'inline' : 'none';
        }

        // Live-update col3 tag label and hidden input as user types in Other field
        if (otherInput) {
            otherInput.addEventListener('input', () => {
                const typed = otherInput.value.trim() || 'Other';
                const h = container.querySelector('input[data-other="1"]');
                if (h) h.value = typed;
                const tagLabel = document.querySelector('#col3-tag-' + col3ListId + '-Other .col3-tag-label');
                if (tagLabel) tagLabel.textContent = typed;
            });
        }

        // Central deselect helper — used by pill click AND col3 × button
        function deselect(val) {
            const isOther = val.toLowerCase() === 'other';
            // Deselect pill visually
            pills.forEach(p => {
                const pVal = p.dataset.skill || p.dataset.field;
                if (pVal === val) p.classList.remove('active-pill');
            });
            // Remove hidden input
            if (isOther) {
                const h = container.querySelector('input[data-other="1"]');
                if (h) h.remove();
                if (otherWrap)  otherWrap.style.display = 'none';
                if (otherInput) otherInput.value = '';
            } else {
                const h = container.querySelector(`input[value="${val}"]`);
                if (h) h.remove();
            }
            // Remove col3 tag
            col3RemoveTag(col3ListId, val);
            updateCounter();
        }

        pills.forEach(pill => {
            pill.addEventListener('click', () => {
                const val     = pill.dataset.skill || pill.dataset.field;
                const label   = pill.textContent.trim();
                const isOther = val.toLowerCase() === 'other';

                if (pill.classList.contains('active-pill')) {
                    // Already selected — deselect
                    deselect(val);
                } else {
                    // Select
                    pill.classList.add('active-pill');

                    if (isOther) {
                        // Show text input
                        if (otherWrap) {
                            otherWrap.style.display = 'block';
                            if (otherInput) setTimeout(() => otherInput.focus(), 50);
                        }
                        // Placeholder hidden input (value updated on typing)
                        const inp = document.createElement('input');
                        inp.type = 'hidden';
                        inp.name = inputName;
                        inp.value = 'Other';
                        inp.setAttribute('data-other', '1');
                        container.appendChild(inp);
                    } else {
                        const inp = document.createElement('input');
                        inp.type  = 'hidden';
                        inp.name  = inputName;
                        inp.value = val;
                        container.appendChild(inp);
                    }

                    // Add tag to col3 — × button uses same deselect helper
                    col3AddTag(col3ListId, val, label, accentColor, (removedVal) => {
                        deselect(removedVal);
                    });
                    updateCounter();
                }
            });
        });
    }

    // Open modal function
    window.openWaitlistModal = function() {
        modal.classList.remove('hidden');
        modal.classList.add('flex');

        // Init pills on first open
        if (!modal.dataset.pillsInit) {
            initOppPills();
            initPills('.skill-pill', 'skills-hidden-inputs', 'skills',  'active-pill', 'skills-count', 'col3-skills', '#a78bfa', 'skill-other-wrap', 'skill-other-input');
            initPills('.field-pill', 'fields-hidden-inputs', 'preferred_field', 'active-pill', 'fields-count', 'col3-fields', '#f472b6', 'field-other-wrap', 'field-other-input');
            modal.dataset.pillsInit = '1';
        }

        // Trigger animation
        setTimeout(() => {
            modal.classList.remove('opacity-0');
            modalContent.classList.remove('scale-75', 'opacity-0');
            modalContent.classList.add('scale-100', 'opacity-100');
        }, 10);

        document.body.style.overflow = 'hidden';
    };

    // Close modal function
    window.closeWaitlistModal = function() {
        modalContent.classList.remove('scale-100', 'opacity-100');
        modalContent.classList.add('scale-75', 'opacity-0');
        modal.classList.add('opacity-0');

        setTimeout(() => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');

            // Reset form
            if (modalForm) {
                modalForm.reset();
                modalForm.classList.remove('hidden');
                if (modalSuccessMessage) modalSuccessMessage.classList.add('hidden');

                // Clear skill/field pill selections
                document.querySelectorAll('.skill-pill.active-pill, .field-pill.active-pill').forEach(p => {
                    p.classList.remove('active-pill');
                });
                // Reset opp pills
                document.querySelectorAll('.opp-pill').forEach(div => {
                    const input = div.previousElementSibling;
                    if (input) input.checked = false;
                    div.classList.remove(
                        'opp-active-volunteer','opp-active-internship',
                        'opp-active-job','opp-active-skillup'
                    );
                });
                // Clear col3 tags and collapse to 2-col
                ['col3-skills','col3-fields'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.innerHTML = '';
                });
                const col3  = document.getElementById('modal-col-3');
                const grid  = document.getElementById('modal-grid');
                const div23 = document.getElementById('divider-23');
                if (col3)  col3.style.display  = 'none';
                if (grid)  grid.style.gridTemplateColumns = 'repeat(2, minmax(0, 1fr))';
                if (div23) div23.style.display = 'none';
                // Reset wrap visibility
                ['col3-skills-wrap','col3-fields-wrap'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.style.display = 'none';
                });
                const empty = document.getElementById('col3-empty');
                if (empty) empty.style.display = 'block';
                ['skills-hidden-inputs','fields-hidden-inputs'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.innerHTML = '';
                });
                // Reset counters
                ['skills-count','fields-count'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.style.display = 'none';
                });
            }
        }, 500);

        document.body.style.overflow = '';
    };

    // Close on Escape — disabled (modal closes via button only)
    // document.addEventListener('keydown', ...)

    // Intercept waitlist links
    document.addEventListener('DOMContentLoaded', function() {
        const waitlistLinks = document.querySelectorAll('a[href*="waitlist"], a[href*="#waitlist"], a[href*="/#waitlist"]');
        waitlistLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                openWaitlistModal();
            });
        });

        // Form submission
        if (modalForm) {
            modalForm.addEventListener('submit', async function(e) {
                e.preventDefault();

                // Validate opportunity type
                const opportunityCheckboxes = modalForm.querySelectorAll('input[name="opportunity_type"]:checked');
                if (opportunityCheckboxes.length === 0) {
                    alert('Please select at least one opportunity type');
                    return;
                }

                // Validate at least one skill and one field
                const skillInputs = document.querySelectorAll('#skills-hidden-inputs input');
                const fieldInputs = document.querySelectorAll('#fields-hidden-inputs input');
                if (skillInputs.length === 0) {
                    alert('Please select at least one skill');
                    return;
                }
                if (fieldInputs.length === 0) {
                    alert('Please select at least one preferred field');
                    return;
                }

                modalSubmitBtn.disabled = true;
                modalBtnText.textContent = 'Processing...';
                modalSubmitBtn.classList.add('opacity-75', 'cursor-not-allowed');

                // Collect data
                const formData = new FormData(modalForm);
                const data = {};

                const opportunityTypes = [];
                opportunityCheckboxes.forEach(cb => opportunityTypes.push(cb.value));
                data.opportunity_types = opportunityTypes;

                const skills = [];
                skillInputs.forEach(i => skills.push(i.value));
                data.skills = skills.join(', ');

                const fields = [];
                fieldInputs.forEach(i => fields.push(i.value));
                data.preferred_field = fields.join(', ');

                for (let [key, value] of formData.entries()) {
                    if (!['opportunity_type','skills','preferred_field'].includes(key)) {
                        data[key] = value;  // captures first_name, last_name, email, phone, country, referral_source
                    }
                }

                data.user_type = 'talent';

                try {
                    const response = await fetch('/api/waitlist', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    const result = await response.json();

                    if (response.ok) {
                        modalForm.classList.add('hidden');
                        modalSuccessMessage.classList.remove('hidden');
                        createConfetti();
                        setTimeout(() => { closeWaitlistModal(); }, 5000);
                    } else {
                        throw new Error(result.detail || 'Something went wrong');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error: ' + error.message);
                    modalSubmitBtn.disabled = false;
                    modalBtnText.textContent = "Join the Waitlist — It's Free 🚀";
                    modalSubmitBtn.classList.remove('opacity-75', 'cursor-not-allowed');
                }
            });
        }
    });

    // Confetti
    function createConfetti() {
        const colors = ['#9333ea', '#ec4899', '#f59e0b', '#10b981', '#3b82f6'];
        for (let i = 0; i < 50; i++) {
            setTimeout(() => {
                const confetti = document.createElement('div');
                confetti.style.cssText = `position:fixed;left:${Math.random()*100}%;top:-10px;
                    width:${Math.random()*10+5}px;height:${Math.random()*10+5}px;
                    background:${colors[Math.floor(Math.random()*colors.length)]};
                    opacity:${Math.random()+0.5};z-index:10000;pointer-events:none;
                    border-radius:${Math.random()>.5?'50%':'0'};transform:rotate(${Math.random()*360}deg)`;
                document.body.appendChild(confetti);
                confetti.animate([
                    { transform: 'translate(0,0) rotate(0deg)', opacity: 1 },
                    { transform: `translate(${Math.random()*200-100}px,${window.innerHeight+20}px) rotate(${Math.random()*720}deg)`, opacity: 0 }
                ], { duration: Math.random()*2000+2000, easing: 'cubic-bezier(0.25,0.46,0.45,0.94)' })
                .onfinish = () => confetti.remove();
            }, i * 30);
        }
    }

    // 3D tilt
    if (modalContent) {
        modalContent.addEventListener('mousemove', function(e) {
            const rect = this.getBoundingClientRect();
            const rotateX = ((e.clientY - rect.top) - rect.height/2) / 50;
            const rotateY = (rect.width/2 - (e.clientX - rect.left)) / 50;
            this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
        });
        modalContent.addEventListener('mouseleave', function() {
            this.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
        });
    }
})();


