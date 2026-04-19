document.addEventListener("DOMContentLoaded", () => {
    // Locate the form and the specific input fields by their ID or attribute
    const form = document.querySelector('form[action="/register"]');
    const passwordInput = document.getElementById("passwordInput");
    const confirmPasswordInput = document.getElementById("confirmPasswordInput");

    if (form) {
        form.addEventListener("submit", (e) => {
            // Remove previous error styling before a new validation attempt
            confirmPasswordInput.classList.remove("is-invalid");

            // Check if passwords match
            if (passwordInput.value !== confirmPasswordInput.value) {
                // 1. Stop the form from being submitted to the server
                e.preventDefault();

                // 2. Add Bootstrap's error class to highlight the input field in red
                confirmPasswordInput.classList.add("is-invalid");

                // 3. Focus the cursor on the confirmation field for immediate correction
                confirmPasswordInput.focus();
            }
            // If passwords match, the script does nothing,
            // and the browser proceeds with the standard POST request.
        });
    }
});