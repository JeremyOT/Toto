$(function() {
  var poll_server = function() {
    var toto = new Toto('http://ec2-107-20-64-184.compute-1.amazonaws.com:9898'), output = $('#chat-view');
    toto.request('receive_message', {}, function(response) {
      output.append($(document.createElement('p')).addClass('message').text(response.message));
      output.animate({
        scrollTop : output.children().last().position().top
      }, 250);
      poll_server();
    }, function(error) {
      setTimeout(poll_server, 5000);
    });
  }, input = $('#chat-input'), send = $('#send-chat');
  poll_server();

  input.keypress(function(event) {
    if(event.keyCode == 13) {
      send.click();
    };
  });
  send.click(function() {
    var toto = new Toto('http://ec2-107-20-64-184.compute-1.amazonaws.com:9898').request('post_message', {
      'message' : input.val()
    });
    input.val('');
  });
});
