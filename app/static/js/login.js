document.addEventListener("DOMContentLoaded", () => {
    // Locate the login form and the submit button
    const loginForm = document.querySelector('form[action="/login"]');
    const submitButton = loginForm ? loginForm.querySelector('button[type="submit"]') : null;

    if (loginForm) {
        loginForm.addEventListener("submit", (e) => {
            const emailInput = document.getElementById("emailInput");
            const passwordInput = document.getElementById("passwordInput");

            // Basic validation to ensure fields are not just empty spaces
            if (!emailInput.value.trim() || !passwordInput.value.trim()) {
                e.preventDefault();
                alert("Please enter both email and password.");
                return;
            }

            // UX Improvement: Disable the button and show a loading state
            // to prevent multiple form submissions while the server processes the request.
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = `
                    <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                    Signing in...
                `;
            }
        });
    }
});