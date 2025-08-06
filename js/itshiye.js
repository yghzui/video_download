//在js中引入,$(document).ready 是等文档加载完成之后再执行jQuery方法，如果文档还没加载完成就执行，有些方法会报错
$(document).ready(function () {
    // $('#preview').load('core/preview.html');
    window.onload = function () {
        // 使用JavaScript判断网页内容的高度是否超过一屏，如果超过则移除固定底部的样式
        var body = document.body;
        var html = document.documentElement;
        var content = document.querySelector('.content');
        var footer = document.querySelector('.footer');

        var totalHeight = body.scrollHeight;
        var windowHeight = html.clientHeight;

        if (totalHeight > windowHeight && content != null) {
            content.style.marginBottom = footer.offsetHeight + 'px';
        }
    };

    $("#downloadArea button").addClass("mt-2");


    // 选择你的输入框，并为它添加一个keypress事件监听器
    $('#urlInput').keypress(function(e) {
        // 判断按下的键是否是Enter键（keyCode为13）
        if (e.keyCode == 13) {
            // 调用你的处理方法
            parseLink();
        }
    });

    // 获取当前页面的URL
    let url = new URL(window.location.href);

    // 使用URLSearchParams从URL中提取参数
    let params = new URLSearchParams(url.search);

    // 获取link参数的值
    let linkValue = params.get('link');
    let token = localStorage.getItem("xzg-userId");
    let refCode = params.get('ref');
    if (isEmpty(token)) {
        if (isNotEmpty(refCode)) {
            localStorage.setItem('xzg-ref-code', refCode);
        }
    }

    // 打印获取到的值
    if (linkValue) {
        $("#urlInput").val(linkValue);
    }

});



// 在全局作用域中定义公共变量
// window.serverUrl = "http://localhost:8899/";
window.serverUrl = "https://www.bestvideow.com/";
// window.serverUrl = "http://119.45.7.180:9712/";
window.downloadRequest;
var xhr;

var processControl = false;


// 解析输入链接
async function parseLink() {
    $("#inputPrompt").hide();
    $('#downloadArea').hide();
    var urlInput = $('#urlInput').val();

    //隐藏下载成功或失败标识
    $("#downloadSuccess,#downloadFail").hide();

    //移除预览中的所有内容
    $("#set-list-preview").empty();

    //禁止点击解析按钮，避免重复点击
    $("#downloadButton").prop('disabled', true);


    // 准备要发送的 JSON 数据
    let jsonData = {};
    //获取用户token
    let token = localStorage.getItem("xzg-userId");
    if (token) {
        jsonData.token = token;
    }

    //提取文本中的URL链接
    var regex = /(http[s]?:\/\/[^\s,，]+)/g;
    var matches = urlInput.match(regex);
    if (matches) {
        urlInput = matches[0];
    } else {
        // $("#inputPrompt").html('解析失败，请重试并检查链接是否有效&emsp;查看&nbsp;<a href="https://www.bestvideow.com/template/tutorial.html" target="_blank">使用教程</a>').show();
        $("#downloadButton").prop('disabled', false);

        let dynamicContent = '解析失败，请重试并检查链接是否有效&emsp;查看&nbsp;<a href="https://www.bestvideow.com/template/tutorial.html" target="_blank">使用教程</a>';
        showButtonModel(dynamicContent);
        return;
    }

    $("#promptText").text("解析中，请稍后……");
    $("#waitAnimation").show();
    jsonData.url = urlInput;

    //请求后缀
    var suffix = "video/parseVideoUrl";

    if (urlInput.indexOf(".bilibili.com") !== -1 || urlInput.indexOf("b23.tv") !== -1|| urlInput.indexOf("bili2233.cn") !== -1) {
        jsonData.platform = "bilibili";
        // suffix = "blbl/parse";
        // var newButton = $('<button id="downloadHdLink" class="btn btn-success ms-1 me-1 mt-2">下载高清</button>');
        // $("#downloadLink").text("下载标清").before(newButton);
        // $("#inputPrompt").text("bilibili视频解析正在修复，给您带来不便，非常抱歉！").show();
        // return;



    } else if (urlInput.indexOf("douyin.com") !== -1) {
        // 提取抖音分享链接
        // var regex = /(https:\/\/www\.douyin\.com\/video\/\d+)|(https:\/\/v\.douyin\.com\/[a-zA-Z0-9]+\/)/g;
        // urlInput = urlInput.match(regex)[0];
        jsonData.platform = "douyin";
        if (urlInput.indexOf("douyin.com/search") !== -1) {
            let dynamicContent = '暂不支持抖音搜索链接下载，请重新输入！';
            showButtonModel(dynamicContent);
            return;
        }
    } else if (urlInput.indexOf("kuaishou.com") !== -1) {
        jsonData.platform = "kuaishou";
    } else if (urlInput.indexOf("pipix.com") !== -1) {
        jsonData.platform = "pipix";
    } else if (urlInput.indexOf("www.xiaohongshu.com") !== -1 || urlInput.indexOf("xhslink.com") !== -1) {
        jsonData.platform = "xhs";
    } else if (urlInput.indexOf("tiktok.com") !== -1) {
        jsonData.platform = "tiktok";
    } else if (urlInput.indexOf("ixigua.com") !== -1) {
        jsonData.platform = "xigua";
    }  else if (urlInput.indexOf("weishi.qq.com") !== -1) {
        jsonData.platform = "weishi";
    } else if (urlInput.indexOf("weibo.com") !== -1) {
        jsonData.platform = "weibo";
    } else if (urlInput.indexOf("jd.com") !== -1 || urlInput.indexOf("3.cn") !== -1) {
        jsonData.platform = "jingdong";
    }  else if (urlInput.indexOf("youtu.be") !== -1 || urlInput.indexOf("youtube.com") !== -1) {
        jsonData.platform = "youtube";
    } else if (urlInput.indexOf("hao123.com") !== -1 || urlInput.indexOf("haokan.baidu.com") !== -1) {
        jsonData.platform = "haokan";
    }  else if (urlInput.indexOf("fb.watch") !== -1 || urlInput.indexOf("facebook.com") !== -1) {
        jsonData.platform = "facebook";
    } else if (urlInput.indexOf("x.com") !== -1 || urlInput.indexOf("twitter.com") !== -1) {
        jsonData.platform = "twitter";
    } else if (urlInput.indexOf("instagram.com") !== -1) {
        jsonData.platform = "instagram";
    } else {
        // $("#inputPrompt").html('解析失败，请重试并检查链接是否有效&emsp;查看&nbsp;<a href="https://www.bestvideow.com/template/tutorial.html" target="_blank">使用教程</a>').show();
        //解除重新解析按钮限制
        $("#downloadButton").prop('disabled', false);
        $("#waitAnimation").hide();

        let dynamicContent = '本站暂不支持您所解析的平台，更多平台正在开发中，感谢您的理解与耐心。';
        showButtonModel(dynamicContent);
        return;
    }

    let params = JSON.stringify(jsonData);

    let encryptParams = await confidential(jsonData);
    jsonData.params= encryptParams;

    console.log(params);
    console.log(encryptParams);

    // 发起 POST 请求
    $.ajax({
        type: "POST",
        url: window.serverUrl + suffix,
        contentType: "application/json", // 指定发送的数据类型
        data: JSON.stringify(jsonData), // 将 JSON 对象转换为字符串
        dataType: "json", // 指定期望的响应数据类型
        xhrFields: {
            withCredentials: true // 携带cookie
        },
        headers: {
            'Authorization': token,
            'timestamg': new Date().getTime()
        },
        success: function (response) {
            var dataObject = response.data;

            window.resultResponse = dataObject;

            if (response.status !== 200) {
                if (response.status === 500 || response.status === 407) {
                    $("#downloadButton").prop('disabled', false);

                    var message = response.message;
                    if ($.trim(message).length !== 0) {
                        if (response.status === 407) {
                            let buttonTwo = '<a href="https://www.bestvideow.com/openmember" target="_blank"><button type="button" class="btn btn-success">去开通</button></a>';
                        } else {
                            let buttonTwo = '<button type="button" class="btn btn-primary" data-bs-dismiss="modal">确定</button>';
                        }
                        showModel(message, buttonTwo);
                    } else {
                        let dynamicContent = '解析失败，请重试并检查链接是否有效&emsp;查看&nbsp;<a href="https://www.bestvideow.com/template/tutorial.html" target="_blank">使用教程</a>';
                        showButtonModel(dynamicContent);
                    }
                    $("#waitAnimation").hide();
                    return;
                }else if (response.status === 748) {

                    //调用验证码

                } else {
                    let dynamicContent = '未知错误，请重试，或&nbsp;<a href="https://www.bestvideow.com/fankui" target="_blank">联系我们</a>';
                    showButtonModel(dynamicContent);
                }
            }

            // 请求成功的回调函数
            console.log("成功收到响应:", response);

            //处理请求成功后的结果
            resultHandle(dataObject);

        },
        error: function (error) {
            $("#waitAnimation").hide();
            if (error.status == 406) {
                alert("请求太过频繁，请稍后重试");
                $('#downloadArea').hide();
            }
            // 失败提示
            let dynamicContent = '解析失败，请重试并检查链接是否有效&emsp;查看&nbsp;<a href="https://www.bestvideow.com/template/tutorial.html" target="_blank">使用教程</a>';
            showButtonModel(dynamicContent);
            //解析完成，允许点击重新解析按钮
            $("#downloadButton").prop('disabled', false);
            console.log("发生错误:", error);
        }
    });



}

//str为需要加密的String字符
function encrypt(str) {
    //密钥--应和后台java解密或是前台js解密的密钥保持一致（16进制）
    var key = CryptoJS.enc.Utf8.parse("bf5941f27ee14d9ba9ebb72d89de5dea");
    //偏移量
    var srcs = CryptoJS.enc.Utf8.parse(str);
    //算法
    var encrypted = CryptoJS.AES.encrypt(srcs, key, { mode : CryptoJS.mode.ECB ,
        padding : CryptoJS.pad.Pkcs7
    });
    //替换--防止值为“1”的情况
    var reg = new RegExp('/', "g");
    return encrypted.toString().replace(reg, "#");
}


// function batchParseLink() {
//     event.preventDefault();
//     var token = localStorage.getItem("xzg-userId");
//
//     var message = "您还未登录或非会员，请开通会员后再使用批量解析！";
//     var buttonTwo = '<a href="https://www.bestvideow.com/openmember" target="_blank"><button type="button" class="btn btn-success">去开通</button></a>';
//     if (!token) {
//         showModel(message, buttonTwo);
//         return;
//     }
//
//     if (!(window.userInfo && window.userInfo.isVip === 1)) {
//         showModel(message, buttonTwo);
//         return;
//     }
//
//     window.location.href = 'https://www.bestvideow.com/main/batch.html';
// }

// 清空下载按钮和输入框
$("#downloadClear").on("click", function (e) {
    // 显示下载按钮，并设置下载链接
    $('#downloadArea').hide();
    $('#urlInput').val("");
    $("#urlInput").focus();

    $('#batchParseText').val("");
    $("#batchParseText").focus();

    //隐藏下载成功或失败标识
    //重新解析，恢复下载点击按钮状态为可点击

    $("#downloadLink,#compressedDownload").prop('disabled', false);

    //移除预览中的所有内容
    $("#set-list-preview,#files").empty();

    //取消正在下载中的任务
    cancelDownload();

    switchStatus(1);

    //将所有动态展示的内容隐藏
    $("#downloadSuccess,#downloadFail,#downloadProgress,#waitAnimation,#inputPrompt").hide();
});


$('#urlInput').focus(function () {
    $("#inputPrompt").hide();
});


function clearInput() {
    $('#urlInput').val("");
    $("#urlInput").focus();
}


//检测用户当前设备
function detectDevice() {
    var userAgent = navigator.userAgent.toLowerCase();
    console.log(userAgent);
    if (userAgent.indexOf("android") !== -1) {
        console.log("用户正在使用安卓设备！");
    } else if (userAgent.indexOf("iphone") !== -1 || userAgent.indexOf("ipad") !== -1 || userAgent.indexOf("ipod") !== -1 || userAgent.indexOf("mac os") !== -1) {
        console.log("用户正在使用苹果设备！");
    } else {
        console.log("用户使用其他设备或浏览器！");
    }
}

//点击下载时触发
$("#downloadLink").on("click", function (e) {
    e.preventDefault(); // 阻止默认行为，防止链接跳转

    //隐藏下载成功或失败标识
    $("#downloadSuccess,#downloadFail,#inputPrompt").hide();

    let result = window.resultResponse;

    //微博、YouTube打开新页面下载
    if ((result.platform === "weibo" || result.platform === "youtube") && result.voideDeatilVoList.length === 1) {
        let fileUrl = result.voideDeatilVoList[0].url;
        window.open(fileUrl, '_blank');
    } else {
        //获取所有选中的文件
        // 获取所有复选框
        // var checkboxes = $('.checkbox');
        // // 获取所有选中的图片
        // var selectedImages = $('.checkbox:checked').closest('.preview-unit').find('.preview-image');
        // $.each(selectedImages, function(index, element){
        //     console.log($(element).attr('src'));
        // });
        // downloadImage(selectedImages);
        // // 判断是否选中了所有图片
        // if (selectedImages.length === checkboxes.length) {
        //     console.log('所有图片都被选中了');
        // } else {
        //     console.log('还有图片未被选中');
        // }

        var selectFileList = downloadPublic();
        if (selectFileList.length < 1) {
            let dynamicContent = '请至少选择一个文件';
            showButtonModel(dynamicContent);
            return;
        }

        $("#downloadSuccess").hide();
        $("#promptText").text("下载中，请稍后……");
        $("#waitAnimation").show();

        //禁止点击下载按钮
        $("#downloadLink,#compressedDownload").prop('disabled', true);

        //单个下载显示下载速度，多个下载的时候不显示速度
        if (selectFileList.length === 1) {

            $("#downloadProgress").show();
            // downloadOneFileReal(fileList);
            downloadOneFileReal(selectFileList);
        } else {
            $("#promptText").text("下载中，请稍后……");
            $("#waitAnimation").show();
            downloadAllFile(selectFileList);
        }

    }




});


//打包下载所有文件,这个方法会存在下载文件不完全就打成压缩包了
function downloadPackage2(fileList) {
    console.log(fileList);
    // 获取所有链接
    var zip = new JSZip();

    // 遍历链接
    $.each(fileList, function (index, element) {
        var link = element.url;
        var fileName = '';
        // 生成随机数作为文件名
        var randomNumber = Math.floor(Math.random() * 1000000); // Adjust the range as needed
        if (element.type === 'video') {
            fileName = 'xzg_' + randomNumber + '.mp4'; // 设置文件名，可以根据实际情况调整
        } else {
            fileName = 'xzg_' + randomNumber + '.png'; // 设置文件名，可以根据实际情况调整
        }

        // 使用ajax进行文件下载
        window.downloadRequest = $.ajax({
            url: link,
            method: 'GET',
            xhrFields: {
                responseType: 'blob' // 设置响应类型为二进制数据流
            },
            success: function (data) {
                // 将文件添加到压缩包中
                zip.file(fileName, data);

                // 如果是最后一个文件，则生成压缩包并下载
                if (index === fileList.length - 1) {
                    zip.generateAsync({type: "blob"})
                        .then(function (content) {
                            // 创建一个a标签
                            var linkElement = document.createElement('a');
                            linkElement.href = window.URL.createObjectURL(content);

                            // 设置下载文件的名称
                            linkElement.download = 'xzg' + randomNumber + '.zip';

                            // 将a标签添加到文档中
                            document.body.appendChild(linkElement);

                            // 模拟点击a标签，开始下载文件
                            linkElement.click();

                            // 移除a标签
                            document.body.removeChild(linkElement);
                            $("#waitAnimation").hide();
                            $("#downloadSuccess").show();

                            //下载完成，放开下载按钮的点击
                            $("#downloadLink,#compressedDownload").prop('disabled', false);
                        });
                }
            },
            error: function () {
                $("#downloadFail").show();
                console.log('文件下载失败');
            }
        });
    });
}

//打包下载所有文件，这个方法解决了  下载文件不完全就打成压缩包 问题
function downloadPackage(fileList) {
    console.log(fileList);
    // 创建一个 JSZip 实例
    var zip = new JSZip();
    var downloadedCount = 0; // 跟踪成功下载的文件数量

    // 遍历文件列表
    $.each(fileList, function (index, element) {
        var link = element.url;
        var fileName = '';
        // 生成随机数作为文件名
        var randomNumber = Math.floor(Math.random() * 1000000); // 调整范围以符合需求
        if (element.type === 'video') {
            fileName = 'xzg_' + randomNumber + '.mp4'; // 设置视频文件名
        } else {
            fileName = 'xzg_' + randomNumber + '.png'; // 设置图片文件名
        }

        // 使用 ajax 进行文件下载
        $.ajax({
            url: link,
            method: 'GET',
            xhrFields: {
                responseType: 'blob' // 设置响应类型为二进制数据流
            },
            success: function (data) {
                // 将文件添加到压缩包中
                zip.file(fileName, data);
                downloadedCount++; // 记录成功下载的文件数量

                // 如果所有文件都已下载完成，则生成压缩包并下载
                if (downloadedCount === fileList.length) {
                    zip.generateAsync({type: "blob"})
                        .then(function (content) {
                            // 创建一个a标签
                            var linkElement = document.createElement('a');
                            linkElement.href = window.URL.createObjectURL(content);

                            var resultObject = window.resultResponse;

                            var zipName = randomNumber;
                            if (resultObject.title) {
                                zipName = resultObject.title;
                            }
                            // 设置下载文件的名称
                            linkElement.download =  zipName + '.zip';

                            // 将a标签添加到文档中
                            document.body.appendChild(linkElement);

                            // 模拟点击a标签，开始下载文件
                            linkElement.click();

                            // 移除a标签
                            document.body.removeChild(linkElement);
                            $("#waitAnimation").hide();
                            $("#downloadSuccess").show();

                            //下载完成，放开下载按钮的点击
                            $("#downloadLink,#compressedDownload").prop('disabled', false);
                        });
                }
            },
            error: function () {
                $("#downloadFail").show();
                console.log('文件下载失败');
            }
        });
    });
}


//遍历下载多个文件
function downloadAllFile(fileList) {

    var voideDeatil = window.resultResponse.voideDeatilVoList[0];
    $.each(fileList, function (index, element) {
        var fileName = '';
        // Generate a random number as a file name
        var randomNumber = Math.floor(Math.random() * 1000000); // Adjust the range as needed

        var fileTitle = voideDeatil.title;
        if (fileTitle !== null && fileTitle !== "" && fileTitle !== "undefined") {
            fileName = fileTitle + index;
        } else {
            fileName = 'xzg_' + randomNumber;
        }

        if (element.type === 'video') {
            fileName = fileName + '.mp4';
        } else {
            fileName = fileName + '.png';
        }

        // Use ajax for file download
        window.downloadRequest = $.ajax({
            url: element.url,
            method: 'GET',
            xhrFields: {
                responseType: 'blob'
            },
            success: function (data) {
                // Create a link element
                var linkElement = document.createElement('a');
                linkElement.href = window.URL.createObjectURL(data);

                // Set the download file name
                linkElement.download = fileName;

                // Add the link element to the document
                document.body.appendChild(linkElement);

                // Simulate clicking the link to start downloading the file
                linkElement.click();

                // Remove the link element from the document
                document.body.removeChild(linkElement);

                $("#waitAnimation").hide();
                $("#downloadSuccess").show();
            },
            error: function () {
                $("#downloadFail").show();
                console.log('File download failed');
            }
        });

    });

    //恢复点击下载按钮
    $("#downloadLink,#compressedDownload").prop('disabled', false);
}


//下载单个文件,并计算下载进度和速率
function downloadOneFileReal(fileList) {
    var voideDeatil = window.resultResponse.voideDeatilVoList[0];

    $("#downloadLink").prop('disabled', true);
    $("#compressedDownload").prop('disabled', true);
    var fileVO = fileList[0];
    var link = fileVO.url;
    var fileName = '';
    // 生成随机数
    var randomNumber = Math.floor(Math.random() * 1000000); // Adjust the range as needed


    var fileTitle = voideDeatil.title;
    if (fileTitle !== null && fileTitle !== "" && fileTitle !== "undefined") {
        fileName = fileTitle;
    } else {
        fileName = 'xzg_' + randomNumber;
    }

    if (fileVO.type === 'video') {
        fileName = fileName + '.mp4';
    } else {
        fileName = fileName + '.png';
    }

    xhr = new XMLHttpRequest();
    xhr.open('GET', link, true);
    xhr.responseType = 'blob';

    var startTime = new Date().getTime();
    var lastLoaded = 0;
    var downloadSpeedInterval;
    var progress;

    xhr.onprogress = function (event) {
        if (event.lengthComputable) {
            progress = (event.loaded / event.total) * 100;
            $('.progress-bar').css('width', progress + '%').attr('aria-valuenow', progress);

            var currentTime = new Date().getTime();
            var elapsedTime = (currentTime - startTime) / 1000;
            var downloadedData = event.loaded - lastLoaded;
            var downloadSpeed = downloadedData / elapsedTime;
            window.downloadRate = formatBytes(downloadSpeed);

            lastLoaded = event.loaded;
            startTime = currentTime;
        }
    };

    xhr.onload = function () {
        clearInterval(downloadSpeedInterval); // 清除定时器
        if (xhr.status === 200) {
            console.log("下载完成");
            var blob = xhr.response;
            var link = $('<a>', {
                href: window.URL.createObjectURL(blob),
                download: fileName
            }).appendTo('body');
            link[0].click();
            link.remove();
            $("#waitAnimation,#downloadProgress").hide();
            $("#downloadSuccess").show();

            //下载完成，恢复点击
            $("#downloadLink,#compressedDownload").prop('disabled', false);

            //下载完成，将进度条清零
            $('.progress-bar').css('width', '0%').attr('aria-valuenow', 0);
        } else {
            console.error('下载失败，HTTP状态码：' + xhr.status);
        }
    };

    xhr.onerror = function () {
        console.error('网络错误');
        console.log("xhr.status=" + xhr.status);

        if (xhr.status === 0) {
            console.error('可能是同源策略阻止了请求');
            window.open(link, '_blank');

            //清除下载中标识，并弹框提示在新页面中下载
            $("#waitAnimation,#downloadProgress").hide();

            //释放点击下载按钮
            $("#downloadLink,#compressedDownload").prop('disabled', false);

            var message = "由于平台下载限制，请在打开的新窗口中下载文件";
            var buttonTwo = '<button type="button" class="btn btn-primary" data-bs-dismiss="modal">确定</button>';
            showModel(message, buttonTwo);
        }
    };

    xhr.send();

    downloadSpeedInterval = setInterval(function () {
        // 每秒执行一次的代码
        // console.log('每秒执行的代码:' + window.downloadRate);
        $('#downloadSpeed').text(window.downloadRate);
        $('.progress-bar').text(Math.floor(progress) + '%');
    }, 1000);

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        var k = 1024 * 600;
        var rete = bytes / k;
        return parseFloat(rete).toFixed(2) + ' MB/s';
    }
}

//压缩下载
$("#compressedDownload").on("click", function () {

    //隐藏下载成功或失败标识
    $("#downloadSuccess,#downloadFail,#inputPrompt").hide();

    var selectFileList = downloadPublic();
    if (selectFileList.length < 1) {
        let dynamicContent = '请至少选择一个文件';
        showButtonModel(dynamicContent);
        return;
    }

    $("#downloadSuccess").hide();
    $("#promptText").text("下载中，请稍后……");
    $("#waitAnimation").show();

    //禁止点击下载按钮
    $("#downloadLink,#compressedDownload").prop('disabled', true);

    downloadPackage(selectFileList);

    // if (selectedImages.length > 1) {
    //     downloadImage(selectedImages);
    //     // 判断是否选中了所有图片
    //     if (selectedImages.length === checkboxes.length) {
    //         console.log('所有图片都被选中了');
    //     } else {
    //         console.log('还有图片未被选中');
    //     }
    // }
});

//选择下载的公共方法
function downloadPublic() {


    var objects = [];

//获取所有复选框选中的文件
    var checkboxes = $('.checkbox');
    // 获取所有选中的图片
    var selectedImages = $('.checkbox:checked').closest('.preview-unit').find('.preview-image');
    $.each(selectedImages, function (index, element) {
        //将所有图片加入集合
        var fileObject = {
            type: "image",
            url: $(element).attr('src')
        };
        objects.push(fileObject);
    });

    // 获取所有选中的视频
    var selectedImages = $('.checkbox:checked').closest('.preview-unit').find('.preview-video');
    $.each(selectedImages, function (index, element) {
        //将所有视频加入集合
        var fileObject = {
            type: "video",
            url: $(element).find('source').attr('src')
        };
        objects.push(fileObject);
    });
    return objects;
};


//取消下载
function cancelDownload() {
    if (xhr && xhr.readyState !== XMLHttpRequest.DONE) {
        // 取消请求
        xhr.abort();
        console.log('下载已取消');
    } else {
        console.log('没有正在进行的下载');
    }

    if (window.downloadRequest) {
        // 取消请求
        window.downloadRequest.abort();
        console.log('文件下载已取消');
    } else {
        console.log('没有正在进行的文件下载');
    }
}




(function () {
    let hm = document.createElement("script");
    hm.src = "https://hm.baidu.com/hm.js?325f36044f263ff86abb4ac69ee4d2db";
    // 设置referrer
    hm.referrerPolicy = 'origin';
    let s = document.getElementsByTagName("script")[0];
    s.parentNode.insertBefore(hm, s);
})();


//展示模态框,最多增加两个按钮，也可以不增加按钮
function showModel(content, buttonOne, buttonTwo) {
    if (content) {
        var modalBody = $('.prompt-content');
        modalBody.empty();
        var modalFooter = $('.modal-footer');
        modalFooter.empty();
        if (buttonOne) {
            modalFooter.append(buttonOne);
        }
        if (buttonTwo) {
            modalFooter.append(buttonTwo);
        }
        modalBody.append(content);
        $('#staticBackdrop').modal('show');
    }

}

//展示模态框,带确定按钮，按钮点击关闭模态框
function showButtonModel(content) {
    if (content) {
        var modalBody = $('#staticBackdrop .prompt-content');
        modalBody.empty();
        var modalFooter = $('#staticBackdrop .modal-footer');
        modalFooter.empty();
        var modalButton = '<button type="button" class="btn btn-primary" data-bs-dismiss="modal">确定</button>';
        modalFooter.append(modalButton);
        modalBody.append(content);
        $('#staticBackdrop').modal('show');
    }

}

