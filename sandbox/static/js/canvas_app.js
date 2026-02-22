(function () {
    const THROTTLE_MS = 50;

    function initCanvas(cursorUrl, csrfToken) {
        const container = document.getElementById('canvas_container');
        if (!container) return;

        let lastSend = 0;

        container.addEventListener('mousemove', (e) => {
            const now = Date.now();
            if (now - lastSend < THROTTLE_MS) return;
            lastSend = now;

            const rect = container.getBoundingClientRect();
            const x = Math.round(e.clientX - rect.left);
            const y = Math.round(e.clientY - rect.top);

            fetch(cursorUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({ cursor_x: x, cursor_y: y }),
            });
        });
    }

    window.initCanvas = initCanvas;
})();
