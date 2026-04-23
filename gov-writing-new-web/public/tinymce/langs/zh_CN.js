(function () {
  if (typeof tinymce === "undefined" || typeof tinymce.addI18n !== "function") {
    return;
  }
  tinymce.addI18n("zh_CN", {
    "Redo": "重做",
    "Undo": "撤销",
    "Bold": "加粗",
    "Italic": "斜体",
    "Underline": "下划线",
    "Bullet list": "项目符号",
    "Numbered list": "编号列表",
    "Insert/edit link": "插入/编辑链接",
    "Table": "表格",
    "Source code": "源码",
    "Search": "查找",
    "Replace": "替换",
    "Word count": "字数统计"
  });
})();
