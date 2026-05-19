import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'REST Database Sync',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(), // Принудительно темная тема для всего приложения
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // Твоя прямая ссылка. Добавляем .json на конце для работы через REST API
  final String _databaseUrl = 
      'https://mess-f848e-default-rtdb.europe-west1.firebasedatabase.app/live_text.json';
  
  String _displayText = "Подключение к базе...";
  http.Client? _client;

  @override
  void initState() {
    super.initState();
    _listenToDatabase();
  }

  void _listenToDatabase() async {
    _client = http.Client();
    final request = http.Request('GET', Uri.parse(_databaseUrl));
    
    // Заголовок для поддержания постоянного соединения (Server-Sent Events)
    request.headers['Accept'] = 'text/event-stream';

    try {
      final response = await _client!.send(request);
      
      response.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .listen((String line) {
        
        // Firebase присылает события в формате "data: { ... }"
        if (line.startsWith('data: ')) {
          final dataString = line.substring(6);
          
          if (dataString != 'null') {
            try {
              final jsonData = jsonDecode(dataString);
              
              // Если это первое подключение или обновление всего узла
              if (jsonData is Map && jsonData.containsKey('data')) {
                final newValue = jsonData['data'];
                setState(() {
                  _displayText = newValue != null ? newValue.toString() : "Узел пуст";
                });
              }
            } catch (e) {
              // Игнорируем технические пакеты от Firebase ("keep-alive" и т.д.)
            }
          } else {
             setState(() {
              _displayText = "Узел 'live_text' не найден";
            });
          }
        }
      });
    } catch (e) {
      setState(() {
        _displayText = "Ошибка сети: $e";
      });
    }
  }

  @override
  void dispose() {
    _client?.close(); // Закрываем сетевое соединение, если закрыли экран
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F0F13), // Глубокий темный фон
      appBar: AppBar(
        title: const Text('Live Text Sync'),
        centerTitle: true,
        backgroundColor: const Color(0xFF060608),
        elevation: 0,
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Text(
            _displayText,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.bold,
              color: Colors.cyanAccent, // Неоновый цвет текста
              shadows: [
                Shadow(
                  blurRadius: 12.0,
                  color: Colors.cyanAccent,
                  offset: Offset(0, 0),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}