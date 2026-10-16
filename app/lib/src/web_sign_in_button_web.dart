import 'package:flutter/widgets.dart';
import 'package:google_sign_in_web/web_only.dart' as web;

/// 網頁版不能呼叫 authenticate()，要用 Google 自己畫的登入按鈕；登入結果走 authenticationEvents。
Widget webSignInButton() => web.renderButton();
