var $ = document.querySelector.bind(document);
var $$ = document.querySelectorAll.bind(document);
function setValue(el, value) {
    // TODO: consider supporting 'data-index' for compound values
    // TODO: change 'data-target' to 'data-value-attr'?
    // TODO: support compound 'data-target' with commas?
    var target = el.getAttribute('data-target') || 'value';
    if (target == 'value') {
        // when no 'data-target' is given, set the 'value' which varies by tag
        if (el.tagName == 'INPUT') {
            if (el.type == 'checkbox') {
                el.checked = !!value;
            }
            else {
                el.value = value;
            }
        }
        else {
            if ('textContent' in el) {
                el.textContent = value; // FF2 support
            }
            else {
                el.innerText = value; // IE6 support
            }
        }
    }
    else {
        var parts = target.split('.');
        if (parts.length == 1) {
            // when some 'data-target' is given, set that attribute
            // e.g.: <name="banner_size" data-target="width"> would run
            //       el.width = value;
            el.setAttribute(target, value);
        }
        else {
            // but if 'data-target' has more than one part, drill down to set it
            // e.g.: <name="banner_size" data-target="style.width"> would run
            //       el.style.width = value;
            var cursor = el;
            while (parts.length > 1) {
                cursor = cursor[parts.shift()];
            }
            cursor[parts[0]] = value;
        }
    }
}
function setValues(el, context) {
    Object.keys(context).forEach(function(name){
        var value = context[name];
        var selector = '[name="'+name+'"]'; // e.g.: [name="team1_color"]
        var items = el.querySelectorAll(selector);
        for (var i = 0; i < items.length; i++) {
            setValue(items[i], value);
        }
        if (el.matches(selector)) {
            setValue(el, value);
        }
    });
}
function render(template, context) {
    template = template || '';
    context = context ||  {};

    var el;
    var html = (template.innerHTML || template).trim();
    if (html.match(/^<tr/)) {
        var container = document.createElement('table');
        container.innerHTML = html;
        el = container.firstChild.firstChild;
    }
    else {
        var container = document.createElement('div');
        container.innerHTML = html;
        el = container.firstChild;
    }

    setValues(el, context);

    return el;
}
