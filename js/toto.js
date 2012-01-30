//////////////////////// from jsSHA - sha1.js /////////////////////////////

/* A JavaScript implementation of the SHA family of hashes, as defined in FIPS
 * PUB 180-2 as well as the corresponding HMAC implementation as defined in
 * FIPS PUB 198a
 *
 * Version 1.3 Copyright Brian Turek 2008-2010
 * Distributed under the BSD License
 * See http://jssha.sourceforge.net/ for more information
 *
 * Several functions taken from Paul Johnson
 */
(function(){var charSize=8,b64pad="",hexCase=0,str2binb=function(a){var b=[],mask=(1<<charSize)-1,length=a.length*charSize,i;for(i=0;i<length;i+=charSize){b[i>>5]|=(a.charCodeAt(i/charSize)&mask)<<(32-charSize-(i%32))}return b},hex2binb=function(a){var b=[],length=a.length,i,num;for(i=0;i<length;i+=2){num=parseInt(a.substr(i,2),16);if(!isNaN(num)){b[i>>3]|=num<<(24-(4*(i%8)))}else{return"INVALID HEX STRING"}}return b},binb2hex=function(a){var b=(hexCase)?"0123456789ABCDEF":"0123456789abcdef",str="",length=a.length*4,i,srcByte;for(i=0;i<length;i+=1){srcByte=a[i>>2]>>((3-(i%4))*8);str+=b.charAt((srcByte>>4)&0xF)+b.charAt(srcByte&0xF)}return str},binb2b64=function(a){var b="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"+"0123456789+/",str="",length=a.length*4,i,j,triplet;for(i=0;i<length;i+=3){triplet=(((a[i>>2]>>8*(3-i%4))&0xFF)<<16)|(((a[i+1>>2]>>8*(3-(i+1)%4))&0xFF)<<8)|((a[i+2>>2]>>8*(3-(i+2)%4))&0xFF);for(j=0;j<4;j+=1){if(i*8+j*6<=a.length*32){str+=b.charAt((triplet>>6*(3-j))&0x3F)}else{str+=b64pad}}}return str},rotl=function(x,n){return(x<<n)|(x>>>(32-n))},parity=function(x,y,z){return x^y^z},ch=function(x,y,z){return(x&y)^(~x&z)},maj=function(x,y,z){return(x&y)^(x&z)^(y&z)},safeAdd_2=function(x,y){var a=(x&0xFFFF)+(y&0xFFFF),msw=(x>>>16)+(y>>>16)+(a>>>16);return((msw&0xFFFF)<<16)|(a&0xFFFF)},safeAdd_5=function(a,b,c,d,e){var f=(a&0xFFFF)+(b&0xFFFF)+(c&0xFFFF)+(d&0xFFFF)+(e&0xFFFF),msw=(a>>>16)+(b>>>16)+(c>>>16)+(d>>>16)+(e>>>16)+(f>>>16);return((msw&0xFFFF)<<16)|(f&0xFFFF)},coreSHA1=function(f,g){var W=[],a,b,c,d,e,T,i,t,appendedMessageLength,H=[0x67452301,0xefcdab89,0x98badcfe,0x10325476,0xc3d2e1f0],K=[0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x5a827999,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x6ed9eba1,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0x8f1bbcdc,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6,0xca62c1d6];f[g>>5]|=0x80<<(24-(g%32));f[(((g+65)>>9)<<4)+15]=g;appendedMessageLength=f.length;for(i=0;i<appendedMessageLength;i+=16){a=H[0];b=H[1];c=H[2];d=H[3];e=H[4];for(t=0;t<80;t+=1){if(t<16){W[t]=f[t+i]}else{W[t]=rotl(W[t-3]^W[t-8]^W[t-14]^W[t-16],1)}if(t<20){T=safeAdd_5(rotl(a,5),ch(b,c,d),e,K[t],W[t])}else if(t<40){T=safeAdd_5(rotl(a,5),parity(b,c,d),e,K[t],W[t])}else if(t<60){T=safeAdd_5(rotl(a,5),maj(b,c,d),e,K[t],W[t])}else{T=safeAdd_5(rotl(a,5),parity(b,c,d),e,K[t],W[t])}e=d;d=c;c=rotl(b,30);b=a;a=T}H[0]=safeAdd_2(a,H[0]);H[1]=safeAdd_2(b,H[1]);H[2]=safeAdd_2(c,H[2]);H[3]=safeAdd_2(d,H[3]);H[4]=safeAdd_2(e,H[4])}return H},jsSHA=function(a,b){this.sha1=null;this.strBinLen=null;this.strToHash=null;if("HEX"===b){if(0!==(a.length%2)){return"TEXT MUST BE IN BYTE INCREMENTS"}this.strBinLen=a.length*4;this.strToHash=hex2binb(a)}else if(("ASCII"===b)||('undefined'===typeof(b))){this.strBinLen=a.length*charSize;this.strToHash=str2binb(a)}else{return"UNKNOWN TEXT INPUT TYPE"}};jsSHA.prototype={getHash:function(a){var b=null,message=this.strToHash.slice();switch(a){case"HEX":b=binb2hex;break;case"B64":b=binb2b64;break;default:return"FORMAT NOT RECOGNIZED"}if(null===this.sha1){this.sha1=coreSHA1(message,this.strBinLen)}return b(this.sha1)},getHMAC:function(a,b,c){var d,keyToUse,i,retVal,keyBinLen,keyWithIPad=[],keyWithOPad=[];switch(c){case"HEX":d=binb2hex;break;case"B64":d=binb2b64;break;default:return"FORMAT NOT RECOGNIZED"}if("HEX"===b){if(0!==(a.length%2)){return"KEY MUST BE IN BYTE INCREMENTS"}keyToUse=hex2binb(a);keyBinLen=a.length*4}else if("ASCII"===b){keyToUse=str2binb(a);keyBinLen=a.length*charSize}else{return"UNKNOWN KEY INPUT TYPE"}if(64<(keyBinLen/8)){keyToUse=coreSHA1(keyToUse,keyBinLen);keyToUse[15]&=0xFFFFFF00}else if(64>(keyBinLen/8)){keyToUse[15]&=0xFFFFFF00}for(i=0;i<=15;i+=1){keyWithIPad[i]=keyToUse[i]^0x36363636;keyWithOPad[i]=keyToUse[i]^0x5C5C5C5C}retVal=coreSHA1(keyWithIPad.concat(this.strToHash),512+this.strBinLen);retVal=coreSHA1(keyWithOPad.concat(retVal),672);return(d(retVal))}};window.jsSHA=jsSHA}());

//////////////////////// end sha1.js /////////////////////////////

function Toto(url) {
  this.url = url;
};

Toto.prototype.sessionID = function() {
  var session = localStorage["TOTO_SESSION_ID" + this.url],
  sessionExpires = localStorage["TOTO_SESSION_EXPIRES" + this.url];
  return sessionExpires > (new Date().getTime()/1000.0) && session;
};

Toto.prototype.userIDStorageKey = function() {
  return "TOTO_USER_ID" + this.url; 
};

Toto.prototype.hmac = function(body) {
  var userID = localStorage["TOTO_USER_ID" + this.url],
  hmac = null;
  if (userID) {
    hmac = new jsSHA(body, "ASCII").getHMAC(userID, "ASCII", "B64");
    switch(hmac.length % 4){
      case 2:
        return hmac + "==";
      case 3:
        return hmac + "=";
    }
  }
  return hmac;
};

Toto.prototype.request = function(method, args, successCallback, errorCallback) {
  var body = JSON.stringify({"method": method, "parameters": args}),
  toto = this,
  session = this.sessionID(),
  hmac = session && this.hmac(body),
  xhr = window.XMLHttpRequest && new XMLHttpRequest();
  if (!xhr) {
    try{
      xhr = new ActiveXObject("Msxml2.XMLHTTP");
    } catch (e) {
      xhr = new ActiveXObject("Microsoft.XMLHTTP");
    }
  }
  xhr.onreadystatechange = function() {
    if(this.readyState == 4 && this.status == 200) {
      var response = JSON.parse(this.responseText),
      responseHmac = this.getResponseHeader("x-toto-hmac"),
      userID = localStorage["TOTO_USER_ID" + toto.url];
      if (responseHmac && userID && toto.hmac(this.responseText) != responseHmac) {
        response.error = {"value": "Invalid response HMAC", "code": 1009};
      }
      if (response.error) {
        if (errorCallback) {
          errorCallback(response.error);
        }
      } else {
        if (successCallback) {
          successCallback(response.result);
        }
      }
    } else if (this.readyState == 4) {
      if (errorCallback) {
        errorCallback({"value": this.responseText, "code": this.status});
      }
    }
  };
  xhr.open("POST",this.url);
  if (hmac) {
    xhr.setRequestHeader("x-toto-session-id", session);
    xhr.setRequestHeader("x-toto-hmac", hmac);
  }
  xhr.setRequestHeader("content-type", "application/json");
  xhr.send(body);
};

Toto.prototype.authenticate = function(userID, password, successCallback, errorCallback) {
  var toto = this;
  this.request("account.login", {"user_id": userID, "password": password }, function(response) {
    localStorage["TOTO_USER_ID" + toto.url] = userID;
    localStorage["TOTO_SESSION_ID" + toto.url] = response.session_id;
    localStorage["TOTO_SESSION_EXPIRES" + toto.url] = response.expires;
    successCallback(response);
  }, errorCallback);
};

Toto.prototype.createAccount = function(userID, password, args, successCallback, errorCallback) {
  var toto = this,
  authArgs = args || {};
  authArgs.user_id = userID;
  authArgs.password = password;
  this.request("account.create", authArgs, function(response) {
    localStorage["TOTO_USER_ID" + toto.url] = userID;
    localStorage["TOTO_SESSION_ID" + toto.url] = response.session_id;
    localStorage["TOTO_SESSION_EXPIRES" + toto.url] = response.expires;
    successCallback(response);
  }, errorCallback);
};
