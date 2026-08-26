document.addEventListener('DOMContentLoaded', function () {
    const canvas = new fabric.Canvas('sketchCanvas');

    // Add parts to canvas on click
    document.querySelectorAll('.part-img').forEach(img => {
        img.addEventListener('click', function () {
            const partSrc = this.dataset.part;
            fabric.Image.fromURL(partSrc, function (oImg) {
                oImg.scale(0.5); // Initial scale
                canvas.add(oImg);
                canvas.centerObject(oImg);
                canvas.setActiveObject(oImg);
            });
        });
    });

    // Delete selected object
    const deleteBtn = document.getElementById('deleteBtn');
    deleteBtn.addEventListener('click', function () {
        const activeObject = canvas.getActiveObject();
        if (activeObject) {
            canvas.remove(activeObject);
        }
    });

    // Download canvas as PNG
    const downloadBtn = document.getElementById('downloadBtn');
    downloadBtn.addEventListener('click', function () {
        const dataURL = canvas.toDataURL({
            format: 'png',
            quality: 1.0
        });
        const link = document.createElement('a');
        link.download = 'forensic_sketch.png';
        link.href = dataURL;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });

     // Handle key press for delete
    window.addEventListener('keydown', function(e) {
        if (e.key === 'Delete' || e.key === 'Backspace') {
            const activeObject = canvas.getActiveObject();
            if (activeObject) {
                canvas.remove(activeObject);
            }
        }
    });
});