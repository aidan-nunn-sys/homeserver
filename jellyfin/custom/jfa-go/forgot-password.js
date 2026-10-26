// JavaScript Injector: send the login page's "Forgot Password" to jfa-go's
// My Account reset instead of Jellyfin's PIN flow (which needs server access).
(function () {
    const ACCOUNT_URL = 'https://<JOIN_HOST>/my/account';
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.btnForgotPassword');
        if (!btn) {
            return;
        }
        e.preventDefault();
        e.stopImmediatePropagation();
        window.location.href = ACCOUNT_URL;
    }, true);
})();
