function single_input() {
    // 点击按钮时获取剪贴板文本并写入输入框
    // 使用 Clipboard API 获取剪贴板文本
    navigator.clipboard.readText()
        .then(function (text) {
            // 将剪贴板文本写入输入框
            $('#single_url').val(text);
        })
        .catch(function (error) {
            console.error('读取剪贴板失败: ', error);
            // 当现代API失败时，提示用户
            alert('无法自动读取剪贴板，请手动粘贴链接(Ctrl+V)。\n错误: ' + error.message);
        });
}

function live_input() {
    navigator.clipboard.readText()
        .then(function (text) {
            $('#live_url').val(text);
        })
        .catch(function (error) {
            console.error('读取剪贴板失败: ', error);
        });
}

function get_parameters() {
    // 获取当前参数设置
    return {
        root: $("#root").val(),
        folder_name: $("#folder_name").val(),
        name_format: $("#name_format").val(),
        date_format: $("#date_format").val(),
        split: $("#split").val(),
        music: $("#music:checked").val(),
        download: $("#download:checked").val(),
        folder_mode: $("#folder_mode:checked").val(),
        storage_format: $("#storage_format").val(),
        run_command: $("#run_command").val(),
        dynamic_cover: $("#dynamic_cover:checked").val(),
        original_cover: $("#original_cover:checked").val(),
        proxies: $("#proxies").val(),
        chunk: $("#chunk").val(),
        max_size: $("#max_size").val(),
        max_retry: $("#max_retry").val(),
        max_pages: $("#max_pages").val(),
        cookie: $("#cookie").val(),
        ffmpeg: $("#ffmpeg").val(),
        disable_selenium: $("#disable_selenium:checked").val(),
    }
}

function update_parameters() {
    $.ajax({
        type: "POST",
        url: "/settings/",
        contentType: "application/json",
        data: JSON.stringify(get_parameters()),
        success: function () {
            window.location.href = "/";
        },
        error: function () {
            alert("保存配置失败！");
        }
    });
}


function single_post(download = false) {
    console.log("调用single_post，download参数:", download);
    const data = {
        url: $("#single_url").val(), download: download
    };
    console.log("发送数据:", data);
    let $text = $("#single_url_text");
    $text.hide();
    $.ajax({
        type: "POST", url: "/single/", contentType: "application/json",  // 设置请求的 Content-Type 为 JSON
        data: JSON.stringify(data),  // 将 JSON 对象转为字符串
        success: function (result) {
            console.log("服务器响应:", result);
            $("#single_state").val(result["text"]);
            
            // 特殊处理图集链接，确保是数组形式
            let downloadLink = result["download"];
            // 如果是字符串但看起来包含多个URL，尝试转换为数组
            if (typeof downloadLink === 'string' && downloadLink.includes('http') && 
                (downloadLink.includes(' ') || downloadLink.includes(','))) {
                console.log("检测到可能的图集字符串，尝试转换为数组:", downloadLink);
                // 尝试通过逗号或空格拆分
                let urls = downloadLink.includes(',') ? downloadLink.split(',') : downloadLink.split(' ');
                // 过滤有效URL
                urls = urls.filter(url => url.trim().startsWith('http'));
                if (urls.length > 1) {
                    console.log("成功将字符串转换为图集数组，长度:", urls.length);
                    downloadLink = urls;
                }
            }
            $("#download_url").data("link", downloadLink);
            
            $("#music_url").data("link", result["music"]);
            $("#origin_url").data("link", result["origin"]);
            $("#dynamic_url").data("link", result["dynamic"]);
            $("#single_preview").attr("src", result["preview"]);
            if (result["author"] !== null) {
                $('#single_url').val("");
            }
            get_images();
            
            // 如果是后台下载模式，显示下载状态
            if (download) {
                console.log("后台下载模式，下载状态:", result["download_status"]);
                alert("下载请求已发送到服务器后台处理" + 
                     (result["download_status"] ? "，状态：" + result["download_status"] : ""));
            }
        }, error: function (xhr, status, error) {
            console.error("请求失败:", status, error);
            console.error("响应文本:", xhr.responseText);
            alert("获取作品数据失败！");
        }
    });
}


function get_download() {
    let link = $("#download_url").data("link");
    console.log("get_download获取到的链接:", link);
    if (!Array.isArray(link)) {
        // 获取视频标题作为文件名 - 如果可用的话
        let videoTitle = $("#single_state").val() || "";
        let filename = "抖音视频";
        
        // 如果状态信息包含成功信息，尝试提取视频作者和描述
        if (videoTitle.includes("获取作品数据成功")) {
            const author = $("#download_url").data("author") || "";
            const desc = $("#download_url").data("desc") || "";
            
            if (author) {
                filename = author + "-";
            }
            
            if (desc) {
                // 截取描述前20个字符作为文件名
                let shortDesc = desc.length > 20 ? desc.substring(0, 20) : desc;
                // 去除文件名中的非法字符
                shortDesc = shortDesc.replace(/[\\/:*?"<>|]/g, "_");
                filename += shortDesc;
            } else {
                filename += new Date().toISOString().slice(0, 10);
            }
        }
        
        // 添加文件扩展名
        filename += ".mp4";
        
        open_link(link, true, filename); // 传入true表示下载模式，并提供文件名
    } else {
        console.log("链接是数组，可能是图集:", link);
        alert('这是图集链接，请使用"显示/隐藏图集下载地址"查看并下载各个图片。');
    }
}

function get_images() {
    console.log("==================== get_images 函数被调用 ====================");
    let link = $("#download_url").data("link");
    let originLink = $("#origin_url").data("link");
    let dynamicLink = $("#dynamic_url").data("link");
    let musicLink = $("#music_url").data("link");
    let $text = $("#single_url_text");
    
    // 如果容器已显示且有内容，则隐藏容器并返回（切换行为）
    if ($text.is(":visible") && $text.children().length > 0) {
        $text.hide();
        console.log("文本容器已隐藏");
        console.log("==================== get_images 函数执行完毕 ====================");
        return;
    }
    
    // 清空当前内容
    $text.empty();
    
    // 检查是数组(图集)还是字符串(视频)
    let isArray = Array.isArray(link);
    
    // 添加标题
    if (isArray && link.length > 0) {
        $text.append('<p><strong>图集链接：</strong></p>');
        
        // 遍历数组创建链接列表
        link.forEach(function (element, index) {
            let paragraph = $("<div>").html('<span style="display:inline-block;width:100px;">图片' + (index + 1) + ':</span> <span style="word-break:break-all;">' + element + '</span>');
            $text.append(paragraph);
        });
    } else {
        // 视频和其他资源链接
        $text.append('<p><strong>视频相关资源链接：</strong></p>');
        
        // 1. 添加视频链接
        $text.append('<div style="margin:10px 0;"><span style="display:inline-block;width:100px;font-weight:bold;">视频:</span> ' + 
            (link ? '<span style="word-break:break-all;">' + link + '</span>' : '<span style="color:gray;">链接不可用</span>') + '</div>');
        
        // 2. 添加静态封面链接
        $text.append('<div style="margin:10px 0;"><span style="display:inline-block;width:100px;font-weight:bold;">静态封面:</span> ' + 
            (originLink ? '<span style="word-break:break-all;">' + originLink + '</span>' : '<span style="color:gray;">链接不可用</span>') + '</div>');
        
        // 3. 添加动态封面链接
        $text.append('<div style="margin:10px 0;"><span style="display:inline-block;width:100px;font-weight:bold;">动态封面:</span> ' + 
            (dynamicLink ? '<span style="word-break:break-all;">' + dynamicLink + '</span>' : '<span style="color:gray;">链接不可用</span>') + '</div>');
        
        // 4. 添加音乐链接
        $text.append('<div style="margin:10px 0;"><span style="display:inline-block;width:100px;font-weight:bold;">音乐:</span> ' + 
            (musicLink ? '<span style="word-break:break-all;">' + musicLink + '</span>' : '<span style="color:gray;">链接不可用</span>') + '</div>');
    }
    
    // 显示容器
    $text.show();
    console.log("文本容器已显示，内容已更新");
    
    console.log("==================== get_images 函数执行完毕 ====================");
}

function get_music() {
    let link = $("#music_url").data("link");
    open_link(link);
}

function get_origin() {
    let link = $("#origin_url").data("link");
    open_link(link);
}

function get_dynamic() {
    let link = $("#dynamic_url").data("link");
    open_link(link);
}

function open_link(link, download = false, filename = "") {
    console.log("open_link被调用, 链接:", link, "下载模式:", download, "文件名:", filename);
    if (link) {
        if (download) {
            console.log("使用下载模式，通过服务器代理下载");
            // 调用服务器端代理API
            $.ajax({
                type: "POST",
                url: "/proxy_download",
                data: JSON.stringify({
                    url: link,
                    filename: filename
                }),
                contentType: "application/json",
                success: function(response) {
                    console.log("服务器响应:", response);
                    if (response.success) {
                        // 显示成功消息
                        alert(`视频已成功下载到服务器\n保存路径: ${response.file_path}`);
                    } else {
                        // 显示错误消息
                        alert(`下载失败: ${response.error || '未知错误'}`);
                    }
                },
                error: function(xhr, status, error) {
                    console.error("代理下载失败:", error);
                    let errorMessage = "下载视频失败";
                    
                    // 尝试解析错误详情
                    try {
                        const response = JSON.parse(xhr.responseText);
                        if (response.error) {
                            errorMessage += `: ${response.error}`;
                            if (response.details) {
                                errorMessage += `\n详细信息: ${response.details}`;
                            }
                        }
                    } catch (e) {
                        errorMessage += `: ${error || '未知错误'}`;
                    }
                    
                    alert(errorMessage);
                }
            });
        } else {
            // 打开模式保持不变
            console.log("使用打开模式，设置target=_blank");
            let a = document.createElement("a");
            a.href = link;
            a.setAttribute("target", "_blank");
            a.setAttribute("rel", "noreferrer noopener");
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                document.body.removeChild(a);
            }, 100);
        }
    } else {
        console.warn("链接为空，无法打开");
        alert("无法下载视频：链接为空");
    }
}

function live_post() {
    const data = {
        url: $("#live_url").val()
    };
    let $text = $("#live_url_text");
    $text.hide();
    $.ajax({
        type: "POST", url: "/live/", contentType: "application/json",  // 设置请求的 Content-Type 为 JSON
        data: JSON.stringify(data),  // 将 JSON 对象转为字符串
        success: function (result) {
            $("#live_state").val(result["text"]);
            let flv = result["flv"];
            let m3u8 = result["m3u8"];
            if (flv) {
                $("#live_url").val("");
                $("#all_url").data({"flv": flv, "m3u8": m3u8});
                $("#best_url").data("link", result["best"]);
                get_all();
            } else {
                $("#all_url").removeData(["flv", "m3u8"]);
                $("#best_url").removeData("link");
                $text.empty();
            }
            $("#live_preview").attr("src", result["preview"]);
        }, error: function () {
            alert("获取直播数据失败！");
        }
    });
}


function get_all() {
    let urls = $("#all_url").data();
    let $text = $("#live_url_text");
    $text.empty();
    for (let key in urls.flv) {
        let paragraph = $("<p>").text(`FLV 清晰度 ${key}: ${urls.flv[key]}`);
        $text.append(paragraph);
    }
    for (let key in urls.m3u8) {
        let paragraph = $("<p>").text(`M3U8 清晰度 ${key}: ${urls.m3u8[key]}`);
        $text.append(paragraph);
    }
    $text.toggle();
}


function get_best() {
    let link = $("#best_url").data("link");
    open_link(link);
}
