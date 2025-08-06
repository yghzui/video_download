// // 定义翻译资源
const resources = {
    'zh-CN': {},
    'en-US': {}
};

// 初始化 i18next
i18next.init({
    lng: 'zh-CN', // 默认语言
    resources: resources,
    returnObjects: true
}, function(err, t) {
    jqueryI18next.init(i18next, $);
    $('body').localize();
});

function updatePlaceholders() {
    // 假设你有以下输入框
    document.getElementById('urlInput').placeholder = i18next.t('content.search_placeholder');
    document.getElementById('account').placeholder = i18next.t('login.emailOrPhone');
    document.getElementById('register_email').placeholder = i18next.t('login.emailOrPhone');
    document.getElementById('modify_email').placeholder = i18next.t('login.emailOrPhone');
    document.getElementById('password').placeholder = i18next.t('login.password');
    document.getElementById('imgCode').placeholder = i18next.t('login.imgCode');
    document.getElementById('modify_imgCode').placeholder = i18next.t('login.imgCode');
    document.getElementById('register_imgCode').placeholder = i18next.t('login.imgCode');
    document.getElementById('register_emailcode').placeholder = i18next.t('login.verificationCode');
    document.getElementById('modify_emailcode').placeholder = i18next.t('login.verificationCode');
    document.getElementById('register_password').placeholder = i18next.t('login.register_password');
    document.getElementById('register_againPWD').placeholder = i18next.t('login.register_password_again');
    document.getElementById('set_password_again').placeholder = i18next.t('login.register_password_again');
    document.getElementById('set_password').placeholder = i18next.t('login.newPassword');
    document.getElementById('urlInput').placeholder = i18next.t('content.search_placeholder');
    document.getElementById('urlInput').placeholder = i18next.t('content.search_placeholder');
    document.getElementById('urlInput').placeholder = i18next.t('content.search_placeholder');
    
    // 如果你有更多的输入框，可以继续这样设置
  }

// 切换语言函数
function changeLanguage(lang) {
    i18next.changeLanguage(lang, (err, t) => {
        if (err) return console.log('something went wrong loading', err);
        jqueryI18next.init(i18next, $);
        $('body').localize();
        updateMetaTags();
        updatePlaceholders();
    });
}

// 更新SEO相关的meta标签
function updateMetaTags() {
    document.title = i18next.t('seo.title');
    $('meta[name="description"]').attr('content', i18next.t('seo.description'));
    $('meta[name="keywords"]').attr('content', i18next.t('seo.keywords'));
}


$(document).ready(function () {
    $.ajax({
        url: '../json/zh-CN.json',
        method: 'GET',
        success: function (response) {
            resources['zh-CN'] = response;
        }
    });
    $.ajax({
        url: '../json/en-US.json',
        method: 'GET',
        success: function (response) {
            resources['en-US'] = response;
        }
    });
    $('#toggleText').click(function () {
        $('#hiddenText').slideToggle();
    });
});