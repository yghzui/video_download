document.addEventListener("DOMContentLoaded", function() {
    const announcementContent = document.getElementById('announcement-content');
    // const announcements = announcementContent.getElementsByTagName('span');
    let currentIndex = 0;

    function showNextAnnouncement() {
        // 隐藏当前公告
        // announcements[currentIndex].style.display = 'none';

        // 切换到下一个公告
        // currentIndex = (currentIndex + 1) % announcements.length;

        // 显示下一个公告
        // announcements[currentIndex].style.display = 'inline-block';
    }

    // 每5秒切换一次公告
    setInterval(showNextAnnouncement, 5000);
});