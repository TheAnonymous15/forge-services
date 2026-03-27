// Waitlist form handling with modern features
document.addEventListener('DOMContentLoaded', function() {
    const waitlistForm = document.getElementById('waitlist-form');
    const successMessage = document.getElementById('success-message');
    const conditionalFields = document.getElementById('conditional-fields');

    if (!waitlistForm) return;

    // Handle user type selection
    const userTypeRadios = document.querySelectorAll('input[name="user_type"]');
    userTypeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            updateConditionalFields(this.value);
        });
    });

    function updateConditionalFields(userType) {
        if (userType === 'talent') {
            conditionalFields.innerHTML = `
                <div class="space-y-4">
                    <div>
                        <label for="skills" class="block text-gray-700 font-semibold mb-2">
                            Top Skills (comma separated)
                        </label>
                        <input type="text" id="skills" name="skills"
                               placeholder="e.g. Python, JavaScript, Data Analysis"
                               class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent text-gray-900">
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label for="linkedin_url" class="block text-gray-700 font-semibold mb-2">
                                LinkedIn Profile
                            </label>
                            <input type="url" id="linkedin_url" name="linkedin_url"
                                   placeholder="https://linkedin.com/in/yourprofile"
                                   class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent text-gray-900">
                        </div>
                        <div>
                            <label for="github_url" class="block text-gray-700 font-semibold mb-2">
                                GitHub Profile
                            </label>
                            <input type="url" id="github_url" name="github_url"
                                   placeholder="https://github.com/yourusername"
                                   class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent text-gray-900">
                        </div>
                    </div>
                </div>
            `;
        } else if (userType === 'employer') {
            conditionalFields.innerHTML = `
                <div class="space-y-4">
                    <div>
                        <label for="company" class="block text-gray-700 font-semibold mb-2">
                            Company Name *
                        </label>
                        <input type="text" id="company" name="company" required
                               class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent text-gray-900">
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label for="company_size" class="block text-gray-700 font-semibold mb-2">
                                Company Size
                            </label>
                            <select id="company_size" name="company_size"
                                    class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent text-gray-900">
                                <option value="">Select size</option>
                                <option value="1-10">1-10 employees</option>
                                <option value="11-50">11-50 employees</option>
                                <option value="51-200">51-200 employees</option>
                                <option value="201-500">201-500 employees</option>
                                <option value="500+">500+ employees</option>
                            </select>
                        </div>
                        <div>
                            <label for="industry" class="block text-gray-700 font-semibold mb-2">
                                Industry
                            </label>
                            <input type="text" id="industry" name="industry"
                                   placeholder="e.g. Technology, Finance"
                                   class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent text-gray-900">
                        </div>
                    </div>

                    <div>
                        <label for="job_title" class="block text-gray-700 font-semibold mb-2">
                            Your Job Title
                        </label>
                        <input type="text" id="job_title" name="job_title"
                               placeholder="e.g. HR Manager, CTO"
                               class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent text-gray-900">
                    </div>
                </div>
            `;
        }
    }

    // Handle form submission
    waitlistForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const submitButton = this.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.innerHTML;

        // Show loading state
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <svg class="animate-spin h-5 w-5 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
        `;

        try {
            const formData = new FormData(this);
            const userType = formData.get('user_type');

            // Build payload
            const payload = {
                email: formData.get('email'),
                user_type: userType,
                first_name: formData.get('first_name'),
                last_name: formData.get('last_name'),
                country: formData.get('country') || null,
            };

            // Add type-specific fields
            if (userType === 'talent') {
                const skillsString = formData.get('skills');
                payload.skills = skillsString ? skillsString.split(',').map(s => s.trim()).filter(Boolean) : [];
                payload.linkedin_url = formData.get('linkedin_url') || null;
                payload.github_url = formData.get('github_url') || null;
            } else if (userType === 'employer') {
                payload.company = formData.get('company');
                payload.company_size = formData.get('company_size') || null;
                payload.industry = formData.get('industry') || null;
                payload.job_title = formData.get('job_title') || null;
            }

            // Determine endpoint
            const endpoint = userType === 'talent'
                ? '/api/v1/waitlist/talent'
                : '/api/v1/waitlist/employer';

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok) {
                // Show success message
                waitlistForm.style.display = 'none';
                successMessage.classList.remove('hidden');

                // Confetti effect (optional)
                if (typeof confetti !== 'undefined') {
                    confetti({
                        particleCount: 100,
                        spread: 70,
                        origin: { y: 0.6 }
                    });
                }
            } else {
                // Show error
                alert('❌ ' + (data.detail || 'Something went wrong. Please try again.'));
                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
            }
        } catch (error) {
            console.error('Error:', error);
            alert('❌ Network error. Please check your connection and try again.');
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
        }
    });
});

