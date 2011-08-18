/**
 * Created by PyCharm.
 * User: ilvar
 * Date: 8/17/11
 * Time: 1:02 PM
 * To change this template use File | Settings | File Templates.
 */
$(function() {
  //автодополнение страны.
  $("input:text[id$=country]").autocomplete({
        source: "/getcountries/",
        minLength: 1,
        delay: 100
  });

  //автодополнение региона.
  $("input:text[id$=region]").autocomplete({
       source: "/getregions/",
       minLength: 2,
       delay: 100,
       select: function(event, ui) {
            var id = $(this).attr('id').replace(/region/g, '');
            $(this).val(ui.item.value.split("/")[0]);
            $('#'+id+'country').val(ui.item.value.split("/")[1]);
            return false;
       },
       focus: function(event, ui) {
            $(this).val(ui.item.value.split("/")[0]);
            $('#'+id+'country').val(ui.item.value.split("/")[1]);
            return false;
       }
  });
  //автодополнение нас. пункта.
  $("input:text[id$=city]").autocomplete({
       source: "/getcities/",
       minLength: 2,
       delay: 100,
       select: function(event, ui) {
           var id = $(this).attr('id').replace(/city/g, '');
           $(this).val(ui.item.value.split("/")[0]);
           $('#'+id+'region').val(ui.item.value.split("/")[1]);
           $('#'+id+'country').val(ui.item.value.split("/")[2]);
           return false;
       },
       focus: function(event, ui) {
           var id = $(this).attr('id').replace(/city/g, '');
           $(this).val(ui.item.value.split("/")[0]);
           $('#'+id+'region').val(ui.item.value.split("/")[1]);
           $('#'+id+'country').val(ui.item.value.split("/")[2]);
           return false;
       }

  });
  //автодополнение улицы.
  $("input:text[id$=street]").autocomplete({
       source: "/getstreets/",
       minLength: 2,
       delay: 100,
       select: function(event, ui) {
           var id = $(this).attr('id').replace(/street$/g, '');
           $(this).val(ui.item.value.split("/")[0]);
           $('#'+id+'city').val(ui.item.value.split("/")[1]);
           $('#'+id+'region').val(ui.item.value.split("/")[2]);
           $('#'+id+'country').val(ui.item.value.split("/")[3]);
           return false;
       },
       focus: function(event, ui) {
           var id = $(this).attr('id').replace(/street$/g, '');
           $(this).val(ui.item.value.split("/")[0]);
           $('#'+id+'city').val(ui.item.value.split("/")[1]);
           $('#'+id+'region').val(ui.item.value.split("/")[2]);
           $('#'+id+'country').val(ui.item.value.split("/")[3]);
           return false;
       }

    });
})