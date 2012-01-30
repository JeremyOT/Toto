$(function() {
  var poll_server = function() {
    var toto = new Toto('http://ec2-107-20-64-184.compute-1.amazonaws.com:9898'), output = $('#chat-view');
    toto.request('receive_message', {}, function(response) {
      output.children().last().append($(document.createElement('p')).addClass('message').text(response.message));
      poll_server();
    }, function(error) {
      setTimeout(poll_server, 5000);
    });
  };
  poll_server();
});
