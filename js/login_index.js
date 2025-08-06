
var img_data;//记录图片验证码
var register_img_data;//记录图片验证码(注册)
var modify_img_data;//记录图片验证码(修改密码)
var _img_data;//记录图片验证码

// 点击打开登录
$('.loginModal').click(function () {
    $('#login_cover').fadeIn(200)
    $('#login_area').show();
    $('#register_area').hide()
    $('#modify_area').hide()
    $('#navbarNav').removeClass('show')
    transImg('verifyImg')
})
// 点击打开注册
$('.registerModal').click(function () {
    $('#login_cover').fadeIn(200)
    $('#register_area').show();
    $('#login_area').hide()
    $('#modify_area').hide()
    $('#navbarNav').removeClass('show')
    transImg('register_verifyImg')
})
//打开登录
function openLogin() {
    console.log("去登录");
    $('#staticBackdrop').modal('hide');
    $('#login_cover').fadeIn(200)
    $('#login_area').show();
    $('#register_area').hide()
    $('#modify_area').hide()
    transImg('verifyImg')
}

//打开注册
function openRegister() {
    console.log("去注册");
    $('#staticBackdrop').modal('hide');
    $('#login_cover').fadeIn(200)
    $('#register_area').show();
    $('#login_area').hide()
    $('#modify_area').hide()
    transImg('register_verifyImg')
}



//点击去登陆
$('.to_login').click(function () {
    $('#login_area').show();
    $('#register_area').hide()
    $('#modify_area').hide();
    transImg('verifyImg')
})
//点击去注册
$('#to_register').click(function () {
    $('#register_area').show();
    $('#login_area').hide()
    $('#modify_area').hide()
    transImg('register_verifyImg')
})

//点击去注册
$('#to_register_account').click(function () {
    $('#register_area').show();
    $('#modify_area').hide();
    $('#login_area').hide();
    transImg('register_verifyImg')
})
//点击去忘记密码
$('#forgetPWD').click(function () {
    $('#modify_area').show();
    $('#register_area').hide();
    $('#login_area').hide();
    transImg('modify_verifyImg')
})
//
$('#forgetPWD_register').click(function () {
    $('#modify_area').show();
    $('#register_area').hide();
    $('#login_area').hide();
    transImg('modify_verifyImg')
})
//获取邮箱验证码 (注册)
$('#get_r_email_code').click(function () {
    if($('#register_imgCode').val()==''){
       return toast('请输入图形验证码')
    }
    get_email_code('register_email', '1', 'get_r_email_code','register_imgCode')
})
//获取邮箱验证码 (修改密码)
$('#get_m_email_code').click(function () {
    if($('#modify_imgCode').val()==''){
        return toast('请输入图形验证码')
     }
    get_email_code('modify_email', '3', 'get_m_email_code','modify_imgCode')
})
//点击关闭登陆
$('#cancel_icon').click(function () {
    $('#login_cover').fadeOut(200)
})

$('#get_vip').click(function(){
    if(!localStorage.getItem('xzg-userId')){
        $('#loginModal').click()
    }
})
//显示隐藏密码
$('.pwd_visible').click(function () {
    if ($(this).parent().prev().attr('type') == 'text') {
        $(this).parent().prev().attr('type', 'password')
        $('.eye_on').show();
        $('.eye_down').hide();
    } else {
        $(this).parent().prev().attr('type', 'text')
        $('.eye_on').hide();
        $('.eye_down').show();
    }

})
function toast(text){
    $('#toast_cover').fadeIn(200);
    $('#toast_cover').html(text)
    setTimeout(()=>{
        $('#toast_cover').fadeOut(200);
    },3000)    
}

// 生成随机字符串
function generateRandomString(length) {
    var characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    var result = '';
    var charactersLength = characters.length;

    for (var i = 0; i < length; i++) {
        result += characters.charAt(Math.floor(Math.random() * charactersLength));
    }

    return result;
}


//获取邮箱验证码
function get_email_code(name, type, btn,imgCode_name) {
    if ($('#' + name).val() == '') {
        alert('请输入注册邮箱')
        return
    }
    if ($('#' + btn).html() != '获取验证码') {
        return
    }
    var count = 60;
    $('#' + btn).addClass('counting');
    var timmer
    $.ajax({
        type: "POST",
        url: window.serverUrl + "user/sendCode",
        contentType: "application/json",
        dataType: "json", // 指定期望的响应数据类型
        data: JSON.stringify({ 'account': $('#' + name).val(),
            'imgCode': $('#' + imgCode_name).val(),
            'imgCodeKey':type=="1"? register_img_data.key:modify_img_data.key,
             "type": type }),
        headers: {
            'Authorization': generateRandomString(15)
        },
        success: function (response) {
            var data = response.data;
            // 请求成功的回调函数
            console.log("成功收到响应:", response);
            //支付成功，移除支付区域所有元素
            if (response.status === 200) {
                alert('验证码已发送，请查收')
                count = 60;

                timmer = setInterval(function () {
                    count--;
                    $('#' + btn).html(count + 's')
                    if (count <= 0) {

                        $('#' + btn).html('获取验证码')
                        $('#' + btn).removeClass('counting')
                        clearInterval(timmer)
                    }
                }, 1000)


            }

            if (response.status !== 200) {
                $('#' + btn).removeClass('counting');
                alert(response.message);
            }

        },
        error: function (error) {
            $('#' + btn).removeClass('counting');
            console.log("发生错误:", error);
        }
    });
}



//点击注册
$('#get_register').click(function () {
    if ($('#register_email').val() == '') {
        alert('请输入注册邮箱/手机号码')
        return
    } else if ($('#register_imgCode').val() == '') {
        alert('请输入图形验证码')
        return
    } else if ($('#register_emailcode').val() == '') {
        alert('请输入邮箱/手机验证码')
        return
    } else if ($('#register_password').val() == '') {
        alert('请输入新密码')
        return
    } else if ($('#register_againPWD').val() == '') {
        alert('请输入新密码')
        return
    } else if ($('#register_againPWD').val() != $('#register_password').val()) {
        alert('两次密码不一致，请核对！')
        return
    }
    let data = {
        "account": $('#register_email').val(),
        "code": $('#register_emailcode').val(),
        "codeKey": register_img_data.key,
        "imgCode": $('#register_imgCode').val(),
        "password": $('#register_password').val(),
        "userName": ""
    }

    let refCode = localStorage.getItem("xzg-ref-code");

    if (isNotEmpty(refCode)) {
        data.refCode = refCode;
    }


    $.ajax({
        type: "POST",
        url: window.serverUrl + "user/register",
        contentType: "application/json",
        dataType: "json", // 指定期望的响应数据类型
        data: JSON.stringify(data),
        success: function (response) {
            var data = response.data;
            // 请求成功的回调函数
            console.log("成功收到响应:", response);
            //支付成功，移除支付区域所有元素
            if (response.status === 200) {

                //注册成功，设置登录状态
                localStorage.setItem("xzg-userId",response.data.token);
                location.reload();
                toast(response.message)
                $('#login_cover').fadeOut(200)
            }

            if (response.status !== 200) {
                alert(response.message);
                transImg('register_verifyImg')
            }

        },
        error: function (error) {

            console.log("发生错误:", error);
        }
    });
})
//点击修改密码
$('#modify_password').click(function () {
    if ($('#modify_email').val() == '') {
        alert('请输入邮箱/手机号码')
        return
    } else if ($('#modify_imgCode').val() == '') {
        alert('请输入图形验证码')
        return
    } else if ($('#modify_emailcode').val() == '') {
        alert('请输入邮箱/手机验证码')
        return
    } else if ($('#set_password').val() == '') {
        alert('请输入新密码')
        return
    } else if ($('#set_password_again').val() == '') {
        alert('请输入新密码')
        return
    } else if ($('#set_password_again').val() != $('#set_password').val()) {
        alert('两次密码不一致，请核对！')
        return
    }
    var data = {
        "account": $('#modify_email').val(),
        "code": $('#modify_emailcode').val(),
        "codeKey": modify_img_data.key,
        "imgCode": $('#modify_imgCode').val(),
        "password": $('#set_password').val(),
        "userName": ""
    }

    $.ajax({
        type: "POST",
        url: window.serverUrl + "user/forgetPassword",
        contentType: "application/json",
        dataType: "json", // 指定期望的响应数据类型
        data: JSON.stringify(data),
        success: function (response) {
            var data = response.data;
            // 请求成功的回调函数
            console.log("成功收到响应:", response);
            //支付成功，移除支付区域所有元素
            if (response.status === 200) {
                toast(response.message)
                $('#login_cover').fadeOut(200)
            }

            if (response.status !== 200) {
                alert(response.message);
                transImg('modify_verifyImg')
            }

        },
        error: function (error) {

            console.log("发生错误:", error);
        }
    });
})



// 点击登录提交
$('#get_login').click(function () {
    if ($('#account').val() == '') {
        alert('请输入账号')
        return
    } else if ($('#password').val() == '') {
        alert('请输入密码')
        return
    } else if ($('#imgCode').val() == '') {
        alert('请输入图形验证码')
        return
    }
    var data = {
        "account": $('#account').val(),
        "codeKey": img_data.key,
        "imgCode": $('#imgCode').val(),
        "password": $('#password').val(),
        "userName": ""
    }
    console.log(JSON.stringify(data))
    $.ajax({
        type: "POST",
        url: window.serverUrl + "user/login",
        contentType: "application/json",
        dataType: "json", // 指定期望的响应数据类型
        data: JSON.stringify(data),
        success: function (response) {
            var data = response.data;
            // 请求成功的回调函数
            console.log("成功收到响应:", response);
            //支付成功，移除支付区域所有元素
            if (response.status === 200) {
                toast(response.message)
                $('#login_cover').fadeOut(200)
                //展示登录注册
                localStorage.setItem("xzg-userId",response.data.token)
                location.reload()
            }

            if (response.status !== 200) {
                alert(response.message);
                transImg('verifyImg')
            }

        },
        error: function (error) {

            console.log("发生错误:", error);
        }
    });

})

// 点击切换图形验证码 (登录)
$('#verifyImg').click(function () {
    transImg('verifyImg')
})
// 点击切换图形验证码 (注册)
$('#register_verifyImg').click(function () {
    transImg('register_verifyImg')
})
// 点击切换图形验证码 (忘记密码)
$('#modify_verifyImg').click(function () {
    transImg('modify_verifyImg')
})

//替换登陆验证码
function transImg(img_name) {
    $.ajax({
        type: "GET",
        url: window.serverUrl + "user/verificationCode",
        dataType: "json", // 指定期望的响应数据类型

        success: function (response) {
            var data = response.data;
            // 请求成功的回调函数
            console.log("成功收到响应:", response);

            //支付成功，移除支付区域所有元素
            if (response.status === 200) {
                $('#' + img_name).attr('src', response.data.image)
                if (img_name == 'verifyImg') {
                    img_data = response.data;
                } else if (img_name == 'register_verifyImg') {
                    register_img_data = response.data
                } else {
                    modify_img_data = response.data
                }



            }

            if (response.status !== 200) {
                alert(response.message);
            }

        },
        error: function (error) {

            console.log("发生错误:", error);
        }
    });
}



