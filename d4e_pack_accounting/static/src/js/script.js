$(document).on('click', '.increment_class', function (ev) {
    document.getElementsByName("customer_no")[0].focus();
    value = document.getElementsByName("customer_no")[0].value ;
    value = value.replace(/\D/g,'');
    if (isNaN(value)) {
            value = 0;
    }
    value = parseInt(value) +1;
    document.getElementsByName("customer_no")[0].value = value ;
    $('input[name*="customer_no"]').trigger("change");
});
