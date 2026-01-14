// ja en ko fr zh ru es pt th de
// "20250322": {
//   ja: {},
//   en: {},
//   ko: {},
//   fr: {},
//   zh: {},
//   ru: {},
//   es: {},
//   pt: {},
//   th: {},
//   de: {}
// },


//マージされるので日付単位で分けて入れたらOK
const resources = {
"20260115": {
"ja":{"settingsReset":"設定を初期化","settingsResetConfirm":"すべての設定とキャッシュを削除します。続行しますか？","tutorialWelcomeTitle":"はじめての漫画作成","tutorialWelcomeBody":"5ステップで基本操作を学びましょう","tutorialStart":"始める","tutorialSkip":"スキップ","tutorialStep1Title":"コマを配置","tutorialStep1Body":"縦向きコマをキャンバスにドラッグ&ドロップします","tutorialStep2Title":"画像を入れる","tutorialStep2Body":"コマに画像をドロップすると自動でフィットします","tutorialStep3Title":"吹き出しを追加","tutorialStep3Body":"吹き出しをドラッグしてコマの上に配置します","tutorialStep4Title":"テキストを入力","tutorialStep4Body":"テキストツールで文字を追加できます","tutorialStep5Title":"完成！","tutorialStep5Body":"キャンバスで自由に編集・調整してください","tutorialNext":"次へ","tutorialFinish":"完了","tutorialExit":"終了","tutorialCompleteTitle":"チュートリアル完了","tutorialCompleteBody":"メニューからいつでも再開できます","tutorialDontShowAgain":"次回から表示しない","tutorialGotIt":"OK","comfyGuideOnlineTitle":"接続成功！","comfyGuideOnlineStep1":"左のタブからWorkflowを選択","comfyGuideOnlineStep2":"テスト生成ボタンで動作確認","comfyGuideOnlineStep3":"エラー時はダウンロードしてComfyUIで確認","comfyGuideOfflineTitle":"ComfyUIに接続できません","comfyGuideOfflineStep1":"ComfyUIを起動してください","comfyGuideOfflineStep2":"URLが正しいか確認してください","comfyGuideOfflineStep3":"デフォルト: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"ノードが見つかりません","comfyGuideNodeErrorMissing":"不足ノード","comfyGuideNodeErrorStep1":"ComfyUI Managerを開く","comfyGuideNodeErrorStep2":"Install Missing Custom Nodesを実行","comfyGuideNodeErrorTip":"Workflowをダウンロード→ComfyUIにドロップでノード詳細確認可能","comfyGuideGenErrorTitle":"生成エラー","comfyGuideGenErrorStep1":"ComfyUIコンソールでエラー確認","comfyGuideGenErrorStep2":"モデルがWorkflowと一致しているか確認","comfyGuideGenErrorExample":"例: SDXL用WorkflowにFluxモデルを設定するとエラーになります","comfyGuideGenErrorStep3":"Workflowの設定値を見直してください"},
"en":{"settingsReset":"Reset Settings","settingsResetConfirm":"All settings and cache will be deleted. Continue?","tutorialWelcomeTitle":"Create Your First Manga","tutorialWelcomeBody":"Learn basics in 5 steps","tutorialStart":"Start","tutorialSkip":"Skip","tutorialStep1Title":"Place Panels","tutorialStep1Body":"Drag & drop panels onto the canvas","tutorialStep2Title":"Add Images","tutorialStep2Body":"Drop images into panels for auto-fit","tutorialStep3Title":"Add Speech Bubbles","tutorialStep3Body":"Drag speech bubbles onto panels","tutorialStep4Title":"Add Text","tutorialStep4Body":"Use text tools to add dialogue","tutorialStep5Title":"Done!","tutorialStep5Body":"Edit and adjust freely on canvas","tutorialNext":"Next","tutorialFinish":"Finish","tutorialExit":"Exit","tutorialCompleteTitle":"Tutorial Complete","tutorialCompleteBody":"Restart anytime from menu","tutorialDontShowAgain":"Don't show again","tutorialGotIt":"OK","comfyGuideOnlineTitle":"Connected!","comfyGuideOnlineStep1":"Select Workflow from left tabs","comfyGuideOnlineStep2":"Click Test Generate to verify","comfyGuideOnlineStep3":"Download workflow to check in ComfyUI if errors","comfyGuideOfflineTitle":"Cannot connect to ComfyUI","comfyGuideOfflineStep1":"Start ComfyUI","comfyGuideOfflineStep2":"Check URL is correct","comfyGuideOfflineStep3":"Default: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"Nodes not found","comfyGuideNodeErrorMissing":"Missing nodes","comfyGuideNodeErrorStep1":"Open ComfyUI Manager","comfyGuideNodeErrorStep2":"Run Install Missing Custom Nodes","comfyGuideNodeErrorTip":"Download workflow → Drop in ComfyUI to see node details","comfyGuideGenErrorTitle":"Generation Error","comfyGuideGenErrorStep1":"Check ComfyUI console for errors","comfyGuideGenErrorStep2":"Verify model matches workflow","comfyGuideGenErrorExample":"Example: Using Flux model with SDXL workflow causes errors","comfyGuideGenErrorStep3":"Review workflow settings"},
"ko":{"settingsReset":"설정 초기화","settingsResetConfirm":"모든 설정과 캐시가 삭제됩니다. 계속하시겠습니까?","tutorialWelcomeTitle":"첫 만화 만들기","tutorialWelcomeBody":"5단계로 기본을 배워봅시다","tutorialStart":"시작","tutorialSkip":"건너뛰기","tutorialStep1Title":"패널 배치","tutorialStep1Body":"패널을 캔버스에 드래그앤드롭","tutorialStep2Title":"이미지 추가","tutorialStep2Body":"패널에 이미지를 드롭하면 자동 맞춤","tutorialStep3Title":"말풍선 추가","tutorialStep3Body":"말풍선을 패널 위에 배치","tutorialStep4Title":"텍스트 입력","tutorialStep4Body":"텍스트 도구로 대사 추가","tutorialStep5Title":"완료!","tutorialStep5Body":"캔버스에서 자유롭게 편집하세요","tutorialNext":"다음","tutorialFinish":"완료","tutorialExit":"종료","tutorialCompleteTitle":"튜토리얼 완료","tutorialCompleteBody":"메뉴에서 언제든지 다시 시작 가능","tutorialDontShowAgain":"다시 표시 안 함","tutorialGotIt":"확인","comfyGuideOnlineTitle":"연결됨!","comfyGuideOnlineStep1":"왼쪽 탭에서 Workflow 선택","comfyGuideOnlineStep2":"테스트 생성으로 확인","comfyGuideOnlineStep3":"오류 시 다운로드하여 ComfyUI에서 확인","comfyGuideOfflineTitle":"ComfyUI에 연결할 수 없음","comfyGuideOfflineStep1":"ComfyUI를 시작하세요","comfyGuideOfflineStep2":"URL이 올바른지 확인","comfyGuideOfflineStep3":"기본값: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"노드를 찾을 수 없음","comfyGuideNodeErrorMissing":"누락된 노드","comfyGuideNodeErrorStep1":"ComfyUI Manager 열기","comfyGuideNodeErrorStep2":"Install Missing Custom Nodes 실행","comfyGuideNodeErrorTip":"Workflow 다운로드 → ComfyUI에 드롭하여 노드 상세 확인","comfyGuideGenErrorTitle":"생성 오류","comfyGuideGenErrorStep1":"ComfyUI 콘솔에서 오류 확인","comfyGuideGenErrorStep2":"모델이 워크플로우와 일치하는지 확인","comfyGuideGenErrorExample":"예: SDXL 워크플로우에 Flux 모델 사용 시 오류 발생","comfyGuideGenErrorStep3":"워크플로우 설정 검토"},
"fr":{"settingsReset":"Réinit. paramètres","settingsResetConfirm":"Tous les paramètres et le cache seront supprimés. Continuer?","tutorialWelcomeTitle":"Créez votre manga","tutorialWelcomeBody":"Apprenez les bases en 5 étapes","tutorialStart":"Démarrer","tutorialSkip":"Passer","tutorialStep1Title":"Placer les cases","tutorialStep1Body":"Glissez-déposez les cases sur le canevas","tutorialStep2Title":"Ajouter des images","tutorialStep2Body":"Déposez les images dans les cases","tutorialStep3Title":"Ajouter des bulles","tutorialStep3Body":"Placez les bulles sur les cases","tutorialStep4Title":"Ajouter du texte","tutorialStep4Body":"Utilisez les outils texte","tutorialStep5Title":"Terminé!","tutorialStep5Body":"Éditez librement sur le canevas","tutorialNext":"Suivant","tutorialFinish":"Terminer","tutorialExit":"Quitter","tutorialCompleteTitle":"Tutoriel terminé","tutorialCompleteBody":"Recommencer depuis le menu","tutorialDontShowAgain":"Ne plus afficher","tutorialGotIt":"OK","comfyGuideOnlineTitle":"Connecté!","comfyGuideOnlineStep1":"Sélectionnez Workflow à gauche","comfyGuideOnlineStep2":"Cliquez Tester pour vérifier","comfyGuideOnlineStep3":"Téléchargez le workflow si erreur","comfyGuideOfflineTitle":"Impossible de connecter à ComfyUI","comfyGuideOfflineStep1":"Démarrez ComfyUI","comfyGuideOfflineStep2":"Vérifiez l'URL","comfyGuideOfflineStep3":"Défaut: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"Nœuds introuvables","comfyGuideNodeErrorMissing":"Nœuds manquants","comfyGuideNodeErrorStep1":"Ouvrez ComfyUI Manager","comfyGuideNodeErrorStep2":"Exécutez Install Missing Custom Nodes","comfyGuideNodeErrorTip":"Téléchargez → Déposez dans ComfyUI pour voir les détails","comfyGuideGenErrorTitle":"Erreur de génération","comfyGuideGenErrorStep1":"Vérifiez la console ComfyUI","comfyGuideGenErrorStep2":"Vérifiez le modèle correspond au workflow","comfyGuideGenErrorExample":"Ex: Utiliser Flux avec workflow SDXL cause des erreurs","comfyGuideGenErrorStep3":"Vérifiez les paramètres du workflow"},
"zh":{"settingsReset":"重置设置","settingsResetConfirm":"将删除所有设置和缓存。继续吗？","tutorialWelcomeTitle":"创建您的第一部漫画","tutorialWelcomeBody":"5步学会基本操作","tutorialStart":"开始","tutorialSkip":"跳过","tutorialStep1Title":"放置分格","tutorialStep1Body":"将分格拖放到画布上","tutorialStep2Title":"添加图片","tutorialStep2Body":"将图片拖入分格自动适配","tutorialStep3Title":"添加对话框","tutorialStep3Body":"将对话框拖到分格上","tutorialStep4Title":"添加文字","tutorialStep4Body":"使用文字工具添加对话","tutorialStep5Title":"完成！","tutorialStep5Body":"在画布上自由编辑调整","tutorialNext":"下一步","tutorialFinish":"完成","tutorialExit":"退出","tutorialCompleteTitle":"教程完成","tutorialCompleteBody":"随时从菜单重新开始","tutorialDontShowAgain":"不再显示","tutorialGotIt":"确定","comfyGuideOnlineTitle":"已连接！","comfyGuideOnlineStep1":"从左侧选项卡选择Workflow","comfyGuideOnlineStep2":"点击测试生成验证","comfyGuideOnlineStep3":"出错时下载到ComfyUI检查","comfyGuideOfflineTitle":"无法连接ComfyUI","comfyGuideOfflineStep1":"启动ComfyUI","comfyGuideOfflineStep2":"检查URL是否正确","comfyGuideOfflineStep3":"默认: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"找不到节点","comfyGuideNodeErrorMissing":"缺失节点","comfyGuideNodeErrorStep1":"打开ComfyUI Manager","comfyGuideNodeErrorStep2":"运行Install Missing Custom Nodes","comfyGuideNodeErrorTip":"下载Workflow→拖入ComfyUI查看节点详情","comfyGuideGenErrorTitle":"生成错误","comfyGuideGenErrorStep1":"检查ComfyUI控制台错误","comfyGuideGenErrorStep2":"确认模型与工作流匹配","comfyGuideGenErrorExample":"例如：SDXL工作流使用Flux模型会报错","comfyGuideGenErrorStep3":"检查工作流设置"},
"ru":{"settingsReset":"Сброс настроек","settingsResetConfirm":"Все настройки и кэш будут удалены. Продолжить?","tutorialWelcomeTitle":"Создайте первую мангу","tutorialWelcomeBody":"Изучите основы за 5 шагов","tutorialStart":"Начать","tutorialSkip":"Пропустить","tutorialStep1Title":"Разместить панели","tutorialStep1Body":"Перетащите панели на холст","tutorialStep2Title":"Добавить изображения","tutorialStep2Body":"Бросьте изображения в панели","tutorialStep3Title":"Добавить облачка","tutorialStep3Body":"Разместите облачка на панелях","tutorialStep4Title":"Добавить текст","tutorialStep4Body":"Используйте текстовые инструменты","tutorialStep5Title":"Готово!","tutorialStep5Body":"Редактируйте свободно на холсте","tutorialNext":"Далее","tutorialFinish":"Готово","tutorialExit":"Выход","tutorialCompleteTitle":"Обучение завершено","tutorialCompleteBody":"Повторить из меню в любое время","tutorialDontShowAgain":"Больше не показывать","tutorialGotIt":"ОК","comfyGuideOnlineTitle":"Подключено!","comfyGuideOnlineStep1":"Выберите Workflow слева","comfyGuideOnlineStep2":"Нажмите Тест для проверки","comfyGuideOnlineStep3":"Скачайте workflow при ошибке","comfyGuideOfflineTitle":"Не удается подключиться к ComfyUI","comfyGuideOfflineStep1":"Запустите ComfyUI","comfyGuideOfflineStep2":"Проверьте URL","comfyGuideOfflineStep3":"По умолчанию: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"Узлы не найдены","comfyGuideNodeErrorMissing":"Отсутствующие узлы","comfyGuideNodeErrorStep1":"Откройте ComfyUI Manager","comfyGuideNodeErrorStep2":"Запустите Install Missing Custom Nodes","comfyGuideNodeErrorTip":"Скачайте → Перетащите в ComfyUI для деталей","comfyGuideGenErrorTitle":"Ошибка генерации","comfyGuideGenErrorStep1":"Проверьте консоль ComfyUI","comfyGuideGenErrorStep2":"Проверьте соответствие модели","comfyGuideGenErrorExample":"Пример: Flux с SDXL workflow вызывает ошибки","comfyGuideGenErrorStep3":"Проверьте настройки workflow"},
"es":{"settingsReset":"Restablecer","settingsResetConfirm":"Se eliminarán todos los ajustes y caché. ¿Continuar?","tutorialWelcomeTitle":"Crea tu primer manga","tutorialWelcomeBody":"Aprende lo básico en 5 pasos","tutorialStart":"Empezar","tutorialSkip":"Omitir","tutorialStep1Title":"Colocar paneles","tutorialStep1Body":"Arrastra paneles al lienzo","tutorialStep2Title":"Agregar imágenes","tutorialStep2Body":"Suelta imágenes en los paneles","tutorialStep3Title":"Agregar bocadillos","tutorialStep3Body":"Coloca bocadillos sobre paneles","tutorialStep4Title":"Agregar texto","tutorialStep4Body":"Usa herramientas de texto","tutorialStep5Title":"¡Listo!","tutorialStep5Body":"Edita libremente en el lienzo","tutorialNext":"Siguiente","tutorialFinish":"Terminar","tutorialExit":"Salir","tutorialCompleteTitle":"Tutorial completado","tutorialCompleteBody":"Reinicia desde el menú","tutorialDontShowAgain":"No mostrar de nuevo","tutorialGotIt":"OK","comfyGuideOnlineTitle":"¡Conectado!","comfyGuideOnlineStep1":"Selecciona Workflow a la izquierda","comfyGuideOnlineStep2":"Clic en Prueba para verificar","comfyGuideOnlineStep3":"Descarga el workflow si hay error","comfyGuideOfflineTitle":"No se puede conectar a ComfyUI","comfyGuideOfflineStep1":"Inicia ComfyUI","comfyGuideOfflineStep2":"Verifica la URL","comfyGuideOfflineStep3":"Predeterminado: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"Nodos no encontrados","comfyGuideNodeErrorMissing":"Nodos faltantes","comfyGuideNodeErrorStep1":"Abre ComfyUI Manager","comfyGuideNodeErrorStep2":"Ejecuta Install Missing Custom Nodes","comfyGuideNodeErrorTip":"Descarga → Suelta en ComfyUI para ver detalles","comfyGuideGenErrorTitle":"Error de generación","comfyGuideGenErrorStep1":"Revisa la consola de ComfyUI","comfyGuideGenErrorStep2":"Verifica que el modelo coincida","comfyGuideGenErrorExample":"Ej: Usar Flux con workflow SDXL causa errores","comfyGuideGenErrorStep3":"Revisa la configuración del workflow"},
"pt":{"settingsReset":"Redefinir","settingsResetConfirm":"Todas as configurações e cache serão excluídos. Continuar?","tutorialWelcomeTitle":"Crie seu primeiro mangá","tutorialWelcomeBody":"Aprenda o básico em 5 passos","tutorialStart":"Iniciar","tutorialSkip":"Pular","tutorialStep1Title":"Posicionar painéis","tutorialStep1Body":"Arraste painéis para a tela","tutorialStep2Title":"Adicionar imagens","tutorialStep2Body":"Solte imagens nos painéis","tutorialStep3Title":"Adicionar balões","tutorialStep3Body":"Posicione balões sobre painéis","tutorialStep4Title":"Adicionar texto","tutorialStep4Body":"Use ferramentas de texto","tutorialStep5Title":"Pronto!","tutorialStep5Body":"Edite livremente na tela","tutorialNext":"Próximo","tutorialFinish":"Concluir","tutorialExit":"Sair","tutorialCompleteTitle":"Tutorial concluído","tutorialCompleteBody":"Reinicie pelo menu a qualquer momento","tutorialDontShowAgain":"Não mostrar novamente","tutorialGotIt":"OK","comfyGuideOnlineTitle":"Conectado!","comfyGuideOnlineStep1":"Selecione Workflow à esquerda","comfyGuideOnlineStep2":"Clique em Testar para verificar","comfyGuideOnlineStep3":"Baixe o workflow se houver erro","comfyGuideOfflineTitle":"Não foi possível conectar ao ComfyUI","comfyGuideOfflineStep1":"Inicie o ComfyUI","comfyGuideOfflineStep2":"Verifique a URL","comfyGuideOfflineStep3":"Padrão: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"Nós não encontrados","comfyGuideNodeErrorMissing":"Nós faltando","comfyGuideNodeErrorStep1":"Abra o ComfyUI Manager","comfyGuideNodeErrorStep2":"Execute Install Missing Custom Nodes","comfyGuideNodeErrorTip":"Baixe → Solte no ComfyUI para ver detalhes","comfyGuideGenErrorTitle":"Erro de geração","comfyGuideGenErrorStep1":"Verifique o console do ComfyUI","comfyGuideGenErrorStep2":"Verifique se o modelo corresponde","comfyGuideGenErrorExample":"Ex: Usar Flux com workflow SDXL causa erros","comfyGuideGenErrorStep3":"Revise as configurações do workflow"},
"th":{"settingsReset":"รีเซ็ตการตั้งค่า","settingsResetConfirm":"การตั้งค่าและแคชทั้งหมดจะถูกลบ ดำเนินการต่อ?","tutorialWelcomeTitle":"สร้างมังงะแรกของคุณ","tutorialWelcomeBody":"เรียนรู้พื้นฐานใน 5 ขั้นตอน","tutorialStart":"เริ่ม","tutorialSkip":"ข้าม","tutorialStep1Title":"วางแผง","tutorialStep1Body":"ลากแผงมาวางบนแคนวาส","tutorialStep2Title":"เพิ่มรูปภาพ","tutorialStep2Body":"วางรูปลงในแผงจะปรับอัตโนมัติ","tutorialStep3Title":"เพิ่มกล่องคำพูด","tutorialStep3Body":"วางกล่องคำพูดบนแผง","tutorialStep4Title":"เพิ่มข้อความ","tutorialStep4Body":"ใช้เครื่องมือข้อความ","tutorialStep5Title":"เสร็จแล้ว!","tutorialStep5Body":"แก้ไขได้อิสระบนแคนวาส","tutorialNext":"ถัดไป","tutorialFinish":"เสร็จ","tutorialExit":"ออก","tutorialCompleteTitle":"บทช่วยสอนเสร็จสิ้น","tutorialCompleteBody":"เริ่มใหม่จากเมนูได้ทุกเมื่อ","tutorialDontShowAgain":"ไม่แสดงอีก","tutorialGotIt":"ตกลง","comfyGuideOnlineTitle":"เชื่อมต่อแล้ว!","comfyGuideOnlineStep1":"เลือก Workflow จากแท็บซ้าย","comfyGuideOnlineStep2":"คลิกทดสอบเพื่อตรวจสอบ","comfyGuideOnlineStep3":"ดาวน์โหลด workflow หากมีข้อผิดพลาด","comfyGuideOfflineTitle":"ไม่สามารถเชื่อมต่อ ComfyUI","comfyGuideOfflineStep1":"เริ่ม ComfyUI","comfyGuideOfflineStep2":"ตรวจสอบ URL","comfyGuideOfflineStep3":"ค่าเริ่มต้น: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"ไม่พบโหนด","comfyGuideNodeErrorMissing":"โหนดที่ขาด","comfyGuideNodeErrorStep1":"เปิด ComfyUI Manager","comfyGuideNodeErrorStep2":"เรียกใช้ Install Missing Custom Nodes","comfyGuideNodeErrorTip":"ดาวน์โหลด → วางใน ComfyUI เพื่อดูรายละเอียด","comfyGuideGenErrorTitle":"ข้อผิดพลาดในการสร้าง","comfyGuideGenErrorStep1":"ตรวจสอบคอนโซล ComfyUI","comfyGuideGenErrorStep2":"ตรวจสอบโมเดลตรงกับ workflow","comfyGuideGenErrorExample":"ตัวอย่าง: ใช้ Flux กับ SDXL workflow จะเกิดข้อผิดพลาด","comfyGuideGenErrorStep3":"ตรวจสอบการตั้งค่า workflow"},
"de":{"settingsReset":"Zurücksetzen","settingsResetConfirm":"Alle Einstellungen und Cache werden gelöscht. Fortfahren?","tutorialWelcomeTitle":"Erstellen Sie Ihren ersten Manga","tutorialWelcomeBody":"Lernen Sie die Grundlagen in 5 Schritten","tutorialStart":"Start","tutorialSkip":"Überspringen","tutorialStep1Title":"Panels platzieren","tutorialStep1Body":"Ziehen Sie Panels auf die Leinwand","tutorialStep2Title":"Bilder hinzufügen","tutorialStep2Body":"Bilder in Panels ablegen","tutorialStep3Title":"Sprechblasen hinzufügen","tutorialStep3Body":"Sprechblasen auf Panels platzieren","tutorialStep4Title":"Text hinzufügen","tutorialStep4Body":"Textwerkzeuge verwenden","tutorialStep5Title":"Fertig!","tutorialStep5Body":"Frei auf der Leinwand bearbeiten","tutorialNext":"Weiter","tutorialFinish":"Fertig","tutorialExit":"Beenden","tutorialCompleteTitle":"Tutorial abgeschlossen","tutorialCompleteBody":"Jederzeit im Menü neu starten","tutorialDontShowAgain":"Nicht mehr anzeigen","tutorialGotIt":"OK","comfyGuideOnlineTitle":"Verbunden!","comfyGuideOnlineStep1":"Workflow links auswählen","comfyGuideOnlineStep2":"Klicken Sie auf Test zum Überprüfen","comfyGuideOnlineStep3":"Workflow bei Fehlern herunterladen","comfyGuideOfflineTitle":"Verbindung zu ComfyUI fehlgeschlagen","comfyGuideOfflineStep1":"ComfyUI starten","comfyGuideOfflineStep2":"URL überprüfen","comfyGuideOfflineStep3":"Standard: http://127.0.0.1:8188","comfyGuideNodeErrorTitle":"Knoten nicht gefunden","comfyGuideNodeErrorMissing":"Fehlende Knoten","comfyGuideNodeErrorStep1":"ComfyUI Manager öffnen","comfyGuideNodeErrorStep2":"Install Missing Custom Nodes ausführen","comfyGuideNodeErrorTip":"Herunterladen → In ComfyUI ablegen für Details","comfyGuideGenErrorTitle":"Generierungsfehler","comfyGuideGenErrorStep1":"ComfyUI-Konsole auf Fehler prüfen","comfyGuideGenErrorStep2":"Modell-Workflow-Übereinstimmung prüfen","comfyGuideGenErrorExample":"Beispiel: Flux mit SDXL-Workflow verursacht Fehler","comfyGuideGenErrorStep3":"Workflow-Einstellungen überprüfen"}
},
"20260111": {
"ja": {"unsupportedProjectFileFormat": "非対応のファイル形式", "unsupportedProjectFileFormatMessage": ".zipまたは.lz4ファイルを選択してください", "OutlinePen": "二重縁取り", "outline1-color": "縁取り1色", "outline2-color": "縁取り2色", "outline1-size": "縁取り1幅", "outline2-size": "縁取り2幅", "outline1-opacity": "縁取り1透明度", "outline2-opacity": "縁取り2透明度"},
"en": {"unsupportedProjectFileFormat": "Unsupported file format", "unsupportedProjectFileFormatMessage": "Please select a .zip or .lz4 file", "OutlinePen": "Double Outline", "outline1-color": "Outline1 Color", "outline2-color": "Outline2 Color", "outline1-size": "Outline1 Width", "outline2-size": "Outline2 Width", "outline1-opacity": "Outline1 Opacity", "outline2-opacity": "Outline2 Opacity"},
"ko": {"unsupportedProjectFileFormat": "지원되지 않는 파일 형식", "unsupportedProjectFileFormatMessage": ".zip 또는 .lz4 파일을 선택하세요", "OutlinePen": "이중 테두리", "outline1-color": "테두리1 색상", "outline2-color": "테두리2 색상", "outline1-size": "테두리1 너비", "outline2-size": "테두리2 너비", "outline1-opacity": "테두리1 불투명도", "outline2-opacity": "테두리2 불투명도"},
"fr": {"unsupportedProjectFileFormat": "Format de fichier non pris en charge", "unsupportedProjectFileFormatMessage": "Veuillez sélectionner un fichier .zip ou .lz4", "OutlinePen": "Double contour", "outline1-color": "Couleur contour1", "outline2-color": "Couleur contour2", "outline1-size": "Largeur contour1", "outline2-size": "Largeur contour2", "outline1-opacity": "Opacité contour1", "outline2-opacity": "Opacité contour2"},
"zh": {"unsupportedProjectFileFormat": "不支持的文件格式", "unsupportedProjectFileFormatMessage": "请选择.zip或.lz4文件", "OutlinePen": "双重描边", "outline1-color": "描边1颜色", "outline2-color": "描边2颜色", "outline1-size": "描边1宽度", "outline2-size": "描边2宽度", "outline1-opacity": "描边1透明度", "outline2-opacity": "描边2透明度"},
"ru": {"unsupportedProjectFileFormat": "Неподдерживаемый формат файла", "unsupportedProjectFileFormatMessage": "Пожалуйста, выберите файл .zip или .lz4", "OutlinePen": "Двойной контур", "outline1-color": "Цвет контура1", "outline2-color": "Цвет контура2", "outline1-size": "Ширина контура1", "outline2-size": "Ширина контура2", "outline1-opacity": "Прозрачность контура1", "outline2-opacity": "Прозрачность контура2"},
"es": {"unsupportedProjectFileFormat": "Formato de archivo no compatible", "unsupportedProjectFileFormatMessage": "Por favor seleccione un archivo .zip o .lz4", "OutlinePen": "Doble contorno", "outline1-color": "Color contorno1", "outline2-color": "Color contorno2", "outline1-size": "Ancho contorno1", "outline2-size": "Ancho contorno2", "outline1-opacity": "Opacidad contorno1", "outline2-opacity": "Opacidad contorno2"},
"pt": {"unsupportedProjectFileFormat": "Formato de arquivo não suportado", "unsupportedProjectFileFormatMessage": "Por favor, selecione um arquivo .zip ou .lz4", "OutlinePen": "Contorno duplo", "outline1-color": "Cor contorno1", "outline2-color": "Cor contorno2", "outline1-size": "Largura contorno1", "outline2-size": "Largura contorno2", "outline1-opacity": "Opacidade contorno1", "outline2-opacity": "Opacidade contorno2"},
"th": {"unsupportedProjectFileFormat": "รูปแบบไฟล์ไม่รองรับ", "unsupportedProjectFileFormatMessage": "กรุณาเลือกไฟล์ .zip หรือ .lz4", "OutlinePen": "เส้นขอบคู่", "outline1-color": "สีขอบ1", "outline2-color": "สีขอบ2", "outline1-size": "ความกว้างขอบ1", "outline2-size": "ความกว้างขอบ2", "outline1-opacity": "ความทึบขอบ1", "outline2-opacity": "ความทึบขอบ2"},
"de": {"unsupportedProjectFileFormat": "Nicht unterstütztes Dateiformat", "unsupportedProjectFileFormatMessage": "Bitte wählen Sie eine .zip- oder .lz4-Datei", "OutlinePen": "Doppelumriss", "outline1-color": "Umriss1 Farbe", "outline2-color": "Umriss2 Farbe", "outline1-size": "Umriss1 Breite", "outline2-size": "Umriss2 Breite", "outline1-opacity": "Umriss1 Deckkraft", "outline2-opacity": "Umriss2 Deckkraft"}
},
"20260114": {
"ja": {"editModeNoObject": "オブジェクトを選択してください", "editModeNotPanel": "パネル（コマ）を選択してください", "editModeNotPolygon": "ポリゴン形式のパネルのみ編集可能です", "editModeNoPoints": "編集可能な頂点がありません", "editModeOn": "コマ編集モードON", "editModeOff": "コマ編集モードOFF"},
"en": {"editModeNoObject": "Please select an object", "editModeNotPanel": "Please select a panel", "editModeNotPolygon": "Only polygon panels can be edited", "editModeNoPoints": "No editable points", "editModeOn": "Panel Edit Mode ON", "editModeOff": "Panel Edit Mode OFF"},
"ko": {"editModeNoObject": "오브젝트를 선택하세요", "editModeNotPanel": "패널을 선택하세요", "editModeNotPolygon": "폴리곤 패널만 편집 가능합니다", "editModeNoPoints": "편집 가능한 점이 없습니다", "editModeOn": "패널 편집 모드 ON", "editModeOff": "패널 편집 모드 OFF"},
"fr": {"editModeNoObject": "Veuillez sélectionner un objet", "editModeNotPanel": "Veuillez sélectionner un panneau", "editModeNotPolygon": "Seuls les panneaux polygones peuvent être modifiés", "editModeNoPoints": "Pas de points modifiables", "editModeOn": "Mode édit. panneau ON", "editModeOff": "Mode édit. panneau OFF"},
"zh": {"editModeNoObject": "请选择对象", "editModeNotPanel": "请选择面板", "editModeNotPolygon": "只能编辑多边形面板", "editModeNoPoints": "没有可编辑的点", "editModeOn": "面板编辑模式 ON", "editModeOff": "面板编辑模式 OFF"},
"ru": {"editModeNoObject": "Выберите объект", "editModeNotPanel": "Выберите панель", "editModeNotPolygon": "Можно редактировать только полигональные панели", "editModeNoPoints": "Нет редактируемых точек", "editModeOn": "Режим редакт. панели ВКЛ", "editModeOff": "Режим редакт. панели ВЫКЛ"},
"es": {"editModeNoObject": "Seleccione un objeto", "editModeNotPanel": "Seleccione un panel", "editModeNotPolygon": "Solo se pueden editar paneles poligonales", "editModeNoPoints": "Sin puntos editables", "editModeOn": "Modo Edic. Panel ON", "editModeOff": "Modo Edic. Panel OFF"},
"pt": {"editModeNoObject": "Selecione um objeto", "editModeNotPanel": "Selecione um painel", "editModeNotPolygon": "Apenas painéis poligonais podem ser editados", "editModeNoPoints": "Sem pontos editáveis", "editModeOn": "Modo Edição Painel ON", "editModeOff": "Modo Edição Painel OFF"},
"th": {"editModeNoObject": "กรุณาเลือกวัตถุ", "editModeNotPanel": "กรุณาเลือกแผง", "editModeNotPolygon": "แก้ไขได้เฉพาะแผงรูปหลายเหลี่ยมเท่านั้น", "editModeNoPoints": "ไม่มีจุดที่แก้ไขได้", "editModeOn": "โหมดแก้ไขพาเนล ON", "editModeOff": "โหมดแก้ไขพาเนล OFF"},
"de": {"editModeNoObject": "Bitte wählen Sie ein Objekt", "editModeNotPanel": "Bitte wählen Sie ein Panel", "editModeNotPolygon": "Nur Polygon-Panels können bearbeitet werden", "editModeNoPoints": "Keine bearbeitbaren Punkte", "editModeOn": "Panel-Bearbeit. ON", "editModeOff": "Panel-Bearbeit. OFF"}
},
"20260113": {
"ja": {"cropEnterToast": "Crop: Enterで完了", "comfyuiWorkflowSettings": "ComfyUI Workflows設定", "sbSelectmode": "選択モード (ESC)"},
"en": {"cropEnterToast": "Crop: Press Enter to complete", "comfyuiWorkflowSettings": "ComfyUI Workflows Settings", "sbSelectmode": "Select Mode (ESC)"},
"ko": {"cropEnterToast": "Crop: Enter로 완료", "comfyuiWorkflowSettings": "ComfyUI Workflows 설정", "sbSelectmode": "선택 모드 (ESC)"},
"fr": {"cropEnterToast": "Crop: Entrée pour terminer", "comfyuiWorkflowSettings": "Paramètres ComfyUI Workflows", "sbSelectmode": "Mode sélection (ESC)"},
"zh": {"cropEnterToast": "裁剪: 按Enter完成", "comfyuiWorkflowSettings": "ComfyUI Workflows设置", "sbSelectmode": "选择模式 (ESC)"},
"ru": {"cropEnterToast": "Обрезка: Enter для завершения", "comfyuiWorkflowSettings": "Настройки ComfyUI Workflows", "sbSelectmode": "Режим выбора (ESC)"},
"es": {"cropEnterToast": "Recortar: Enter para completar", "comfyuiWorkflowSettings": "Configuración ComfyUI Workflows", "sbSelectmode": "Modo selección (ESC)"},
"pt": {"cropEnterToast": "Cortar: Enter para concluir", "comfyuiWorkflowSettings": "Configurações ComfyUI Workflows", "sbSelectmode": "Modo seleção (ESC)"},
"th": {"cropEnterToast": "ครอป: กด Enter เพื่อเสร็จสิ้น", "comfyuiWorkflowSettings": "การตั้งค่า ComfyUI Workflows", "sbSelectmode": "โหมดเลือก (ESC)"},
"de": {"cropEnterToast": "Zuschneiden: Enter zum Abschließen", "comfyuiWorkflowSettings": "ComfyUI Workflows Einstellungen", "sbSelectmode": "Auswahlmodus (ESC)"}
},
"20260112": {
"ja": {"op_cancel": "キャンセル", "op_cancelling": "キャンセル中...", "op_cancelled": "キャンセル済み", "op_waitingTask": "現在のタスクを待機中..."},
"en": {"op_cancel": "Cancel", "op_cancelling": "Cancelling...", "op_cancelled": "Cancelled", "op_waitingTask": "Waiting for current task..."},
"ko": {"op_cancel": "취소", "op_cancelling": "취소 중...", "op_cancelled": "취소됨", "op_waitingTask": "현재 작업 대기 중..."},
"fr": {"op_cancel": "Annuler", "op_cancelling": "Annulation...", "op_cancelled": "Annulé", "op_waitingTask": "En attente de la tâche en cours..."},
"zh": {"op_cancel": "取消", "op_cancelling": "取消中...", "op_cancelled": "已取消", "op_waitingTask": "等待当前任务..."},
"ru": {"op_cancel": "Отмена", "op_cancelling": "Отмена...", "op_cancelled": "Отменено", "op_waitingTask": "Ожидание текущей задачи..."},
"es": {"op_cancel": "Cancelar", "op_cancelling": "Cancelando...", "op_cancelled": "Cancelado", "op_waitingTask": "Esperando tarea actual..."},
"pt": {"op_cancel": "Cancelar", "op_cancelling": "Cancelando...", "op_cancelled": "Cancelado", "op_waitingTask": "Aguardando tarefa atual..."},
"th": {"op_cancel": "ยกเลิก", "op_cancelling": "กำลังยกเลิก...", "op_cancelled": "ยกเลิกแล้ว", "op_waitingTask": "รอการทำงานปัจจุบัน..."},
"de": {"op_cancel": "Abbrechen", "op_cancelling": "Abbrechen...", "op_cancelled": "Abgebrochen", "op_waitingTask": "Warte auf aktuelle Aufgabe..."}
},
"20250413": {
"ja": {"upscaleButton": "画像を高解像度化します", "cropButton": "Crop", "importButton": "インポート", "exitModeButton": "モード解除 (ESC)"},
"en": {"upscaleButton": "Upscale image", "cropButton": "Crop", "importButton": "Import", "exitModeButton": "Exit Mode (ESC)"},
"ko": {"upscaleButton": "이미지 확대", "cropButton": "자르기", "importButton": "가져오기", "exitModeButton": "모드 해제 (ESC)"},
"fr": {"upscaleButton": "Améliorer l'image", "cropButton": "Rogner", "importButton": "Importer", "exitModeButton": "Quitter (ESC)"},
"zh": {"upscaleButton": "提升图像分辨率", "cropButton": "裁剪", "importButton": "导入", "exitModeButton": "退出模式 (ESC)"},
"ru": {"upscaleButton": "Увеличить разрешение", "cropButton": "Обрезка", "importButton": "Импорт", "exitModeButton": "Выход (ESC)"},
"es": {"upscaleButton": "Mejorar resolución", "cropButton": "Recorte", "importButton": "Importar", "exitModeButton": "Salir (ESC)"},
"pt": {"upscaleButton": "Aumentar resolução", "cropButton": "Cortar", "importButton": "Importar", "exitModeButton": "Sair (ESC)"},
"th": {"upscaleButton": "เพิ่มความละเอียดภาพ", "cropButton": "ครอป", "importButton": "นำเข้า", "exitModeButton": "ออก (ESC)"},
"de": {"upscaleButton": "Bild verbessern", "cropButton": "Zuschneiden", "importButton": "Importieren", "exitModeButton": "Beenden (ESC)"}
},

"20250322": {
ja: {missingNode:"ノード情報無し", missingDescription:"ComfyUI接続未経験かノード無し。WorkflowをダウンロードしてComfyUIに適用してComfyUI ManagerからInstall Missing Custom Nodesを実行してください"},
en: {missingNode:"No node info", missingDescription:"No ComfyUI connection experience or no nodes. Download Workflow, apply to ComfyUI and run Install Missing Custom Nodes from ComfyUI Manager"},
ko: {missingNode:"노드 정보 없음", missingDescription:"ComfyUI 연결 경험이 없거나 노드가 없습니다. 워크플로우를 다운로드하여 ComfyUI에 적용하고 ComfyUI Manager에서 누락된 사용자 정의 노드 설치를 실행하세요"},
fr: {missingNode:"Aucune info de nœud", missingDescription:"Pas d'expérience de connexion ComfyUI ou nœuds manquants. Téléchargez le workflow, appliquez-le à ComfyUI et exécutez Installer les nœuds personnalisés manquants depuis le gestionnaire ComfyUI"},
zh: {missingNode:"无节点信息", missingDescription:"未连接ComfyUI或节点缺失。下载工作流，应用到ComfyUI并从ComfyUI管理器运行安装缺失的自定义节点"},
ru: {missingNode:"Нет информации о узле", missingDescription:"Нет опыта подключения к ComfyUI или отсутствуют узлы. Загрузите рабочий процесс, примените его к ComfyUI и запустите установку отсутствующих пользовательских узлов из менеджера ComfyUI"},
es: {missingNode:"Sin información de nodo", missingDescription:"Sin experiencia de conexión a ComfyUI o nodos ausentes. Descargue el flujo de trabajo, aplíquelo a ComfyUI y ejecute Instalar nodos personalizados faltantes desde el Administrador de ComfyUI"},
pt: {missingNode:"Sem informação de nó", missingDescription:"Sem experiência de conexão ComfyUI ou nós ausentes. Baixe o fluxo de trabalho, aplique ao ComfyUI e execute Instalar nós personalizados ausentes do Gerenciador ComfyUI"},
th: {missingNode:"ไม่มีข้อมูลโหนด", missingDescription:"ไม่มีประสบการณ์การเชื่อมต่อ ComfyUI หรือไม่มีโหนด ดาวน์โหลดเวิร์กโฟลว์ ใช้กับ ComfyUI และเรียกใช้การติดตั้งโหนดที่ขาดหายไปจาก ComfyUI Manager"},
de: {missingNode:"Keine Knoteninfo", missingDescription:"Keine ComfyUI-Verbindungserfahrung oder keine Knoten. Workflow herunterladen, auf ComfyUI anwenden und Fehlende benutzerdefinierte Knoten installieren vom ComfyUI Manager ausführen"}
},
"20250321": {
 ja: {
 rought_error:"不明なエラー",
 rough_target:"ラフ対象が選択されていません",
 rough_target_message:"ラフは図形、アイコン、フリー吹き出しに適用できます。",
 "Rough":"ラフ(β)",
 "strokeColor":"線色",
 "fillStyle":"塗りスタイル",
 "fill_style":"塗りスタイル",
 "fillWeight":"塗りの太さ",
 "rough_style":"基本スタイル",
 "roughness":"ラフ度",
 "bowing":"曲がり具合",
 "strokeWidth":"線の太さ",
 "rough_hachure":"ハッチング設定",
 "hachureAngle":"ハッチング角度",
 "hachureGap":"ハッチング間隔",
 "rough_curve":"曲線",
 "curveStepCount":"曲線数",
 "curveFitting":"曲線フィット",
 "simplification":"単純化",
 "rough_on_off":"ラフ ON/OFF",
 "rough_on":"ラフ ON",
 "rough_off":"ラフ OFF",
 "Multi":"マルチストローク",
 "MultiFill":"マルチフィル",    
 side_label_rough:"ラフ", 
 auto_generate:"自動生成", 
 prompt:"プロンプト(β)", 
 prompt_gallery:"プロンプトギャラリー", 
 loading_image:"読み込み中", 
 image_load_error:"画像がありません"
 },
 en: {
 rought_error:"Unknown error",
 rough_target:"No rough target selected",
 rough_target_message:"Rough can be applied to shapes, icons, and free bubbles.",
 "Rough":"Rough(β)",
 "strokeColor":"Stroke color",
 "fillStyle":"Fill style",
 "fill_style":"Fill style",
 "fillWeight":"Fill weight",
 "rough_style":"Basic style",
 "roughness":"Roughness",
 "bowing":"Bowing",
 "strokeWidth":"Stroke width",
 "rough_hachure":"Hachure settings",
 "hachureAngle":"Hachure angle",
 "hachureGap":"Hachure gap",
 "rough_curve":"Curve",
 "curveStepCount":"Curve steps",
 "curveFitting":"Curve fitting",
 "simplification":"Simplification",
 "rough_on_off":"Rough ON/OFF",
 "rough_on":"Rough ON",
 "rough_off":"Rough OFF",
 "Multi":"Multi-stroke",
 "MultiFill":"Multi-fill",
 side_label_rough:"Rough", 
 auto_generate:"Auto Generate", 
 prompt:"Prompt(β)", 
 prompt_gallery:"Prompt Gallery", 
 loading_image:"Loading", 
 image_load_error:"No image"
 },
 ko: {
 rought_error:"알 수 없는 오류",
 rough_target:"선택된 러프 대상 없음",
 rough_target_message:"러프는 도형, 아이콘, 자유 말풍선에 적용할 수 있습니다.",
 "Rough":"러프(β)",
 "strokeColor":"선 색상",
 "fillStyle":"채우기 스타일",
 "fill_style":"채우기 스타일",
 "fillWeight":"채우기 두께",
 "rough_style":"기본 스타일",
 "roughness":"거친 정도",
 "bowing":"굽힘 정도",
 "strokeWidth":"선 두께",
 "rough_hachure":"해칭 설정",
 "hachureAngle":"해칭 각도",
 "hachureGap":"해칭 간격",
 "rough_curve":"곡선",
 "curveStepCount":"곡선 단계",
 "curveFitting":"곡선 맞춤",
 "simplification":"단순화",
 "rough_on_off":"러프 켜기/끄기",
 "rough_on":"러프 켜기",
 "rough_off":"러프 끄기",
 "Multi":"멀티 스트로크",
 "MultiFill":"멀티 채우기",
 side_label_rough:"러프", 
 auto_generate:"자동 생성", 
 prompt:"프롬프트(β)", 
 prompt_gallery:"프롬프트 갤러리", 
 loading_image:"로딩 중", 
 image_load_error:"이미지 없음"
 },
 fr: {
 rought_error:"Erreur inconnue",
 rough_target:"Aucune cible brute sélectionnée",
 rough_target_message:"L'effet brut peut être appliqué aux formes, icônes et bulles libres.",
 "Rough":"Brut(β)",
 "strokeColor":"Couleur de trait",
 "fillStyle":"Style de remplissage",
 "fill_style":"Style de remplissage",
 "fillWeight":"Épaisseur de remplissage",
 "rough_style":"Style de base",
 "roughness":"Rugosité",
 "bowing":"Courbure",
 "strokeWidth":"Épaisseur de trait",
 "rough_hachure":"Paramètres de hachure",
 "hachureAngle":"Angle de hachure",
 "hachureGap":"Espacement de hachure",
 "rough_curve":"Courbe",
 "curveStepCount":"Nombre de pas",
 "curveFitting":"Ajustement de courbe",
 "simplification":"Simplification",
 "rough_on_off":"Brut ON/OFF",
 "rough_on":"Brut ON",
 "rough_off":"Brut OFF",
 "Multi":"Multi-traits",
 "MultiFill":"Multi-remplissage",
 side_label_rough:"Brut", 
 auto_generate:"Génération auto", 
 prompt:"Invite(β)", 
 prompt_gallery:"Galerie d'invites", 
 loading_image:"Chargement", 
 image_load_error:"Pas d'image"
 },
 zh: {
 rought_error:"未知错误",
 rough_target:"未选择粗糙目标",
 rough_target_message:"粗糙效果可应用于形状、图标和自由气泡。",
 "Rough":"粗糙(β)",
 "strokeColor":"线条颜色",
 "fillStyle":"填充样式",
 "fill_style":"填充样式",
 "fillWeight":"填充厚度",
 "rough_style":"基本样式",
 "roughness":"粗糙度",
 "bowing":"弯曲度",
 "strokeWidth":"线条宽度",
 "rough_hachure":"阴影设置",
 "hachureAngle":"阴影角度",
 "hachureGap":"阴影间距",
 "rough_curve":"曲线",
 "curveStepCount":"曲线步数",
 "curveFitting":"曲线拟合",
 "simplification":"简化",
 "rough_on_off":"粗糙开/关",
 "rough_on":"粗糙开",
 "rough_off":"粗糙关",
 "Multi":"多重线条",
 "MultiFill":"多重填充",
 side_label_rough:"粗糙", 
 auto_generate:"自动生成", 
 prompt:"提示(β)", 
 prompt_gallery:"提示画廊", 
 loading_image:"加载中", 
 image_load_error:"没有图像"
 },
 ru: {
 rought_error:"Неизвестная ошибка",
 rough_target:"Не выбрана цель для эффекта",
 rough_target_message:"Эффект можно применить к фигурам, иконкам и свободным пузырям.",
 "Rough":"Эффект(β)",
 "strokeColor":"Цвет линии",
 "fillStyle":"Стиль заливки",
 "fill_style":"Стиль заливки",
 "fillWeight":"Вес заливки",
 "rough_style":"Базовый стиль",
 "roughness":"Шероховатость",
 "bowing":"Изгиб",
 "strokeWidth":"Толщина линии",
 "rough_hachure":"Настройки штриховки",
 "hachureAngle":"Угол штриховки",
 "hachureGap":"Интервал штриховки",
 "rough_curve":"Кривая",
 "curveStepCount":"Шаги кривой",
 "curveFitting":"Подгонка кривой",
 "simplification":"Упрощение",
 "rough_on_off":"Эффект ВКЛ/ВЫКЛ",
 "rough_on":"Эффект ВКЛ",
 "rough_off":"Эффект ВЫКЛ",
 "Multi":"Мульти-штрих",
 "MultiFill":"Мульти-заливка",
 side_label_rough:"Эффект", 
 auto_generate:"Автогенерация", 
 prompt:"Промпт(β)", 
 prompt_gallery:"Галерея промптов", 
 loading_image:"Загрузка", 
 image_load_error:"Нет изображения"
 },
 es: {
 rought_error:"Error desconocido",
 rough_target:"No hay objetivo rugoso seleccionado",
 rough_target_message:"El efecto rugoso se puede aplicar a formas, iconos y burbujas libres.",
 "Rough":"Rugoso(β)",
 "strokeColor":"Color de trazo",
 "fillStyle":"Estilo de relleno",
 "fill_style":"Estilo de relleno",
 "fillWeight":"Peso de relleno",
 "rough_style":"Estilo básico",
 "roughness":"Rugosidad",
 "bowing":"Curvatura",
 "strokeWidth":"Grosor de trazo",
 "rough_hachure":"Ajustes de rayado",
 "hachureAngle":"Ángulo de rayado",
 "hachureGap":"Espacio de rayado",
 "rough_curve":"Curva",
 "curveStepCount":"Pasos de curva",
 "curveFitting":"Ajuste de curva",
 "simplification":"Simplificación",
 "rough_on_off":"Rugoso ON/OFF",
 "rough_on":"Rugoso ON",
 "rough_off":"Rugoso OFF",
 "Multi":"Multi-trazo",
 "MultiFill":"Multi-relleno",
 side_label_rough:"Rugoso", 
 auto_generate:"Generación auto", 
 prompt:"Prompt(β)", 
 prompt_gallery:"Galería de prompts", 
 loading_image:"Cargando", 
 image_load_error:"No hay imagen"
 },
 pt: {
 rought_error:"Erro desconhecido",
 rough_target:"Nenhum alvo áspero selecionado",
 rough_target_message:"O efeito áspero pode ser aplicado a formas, ícones e balões livres.",
 "Rough":"Áspero(β)",
 "strokeColor":"Cor do traço",
 "fillStyle":"Estilo de preenchimento",
 "fill_style":"Estilo de preenchimento",
 "fillWeight":"Peso do preenchimento",
 "rough_style":"Estilo básico",
 "roughness":"Aspereza",
 "bowing":"Curvatura",
 "strokeWidth":"Espessura do traço",
 "rough_hachure":"Config. de hachura",
 "hachureAngle":"Ângulo de hachura",
 "hachureGap":"Espaço de hachura",
 "rough_curve":"Curva",
 "curveStepCount":"Passos da curva",
 "curveFitting":"Ajuste de curva",
 "simplification":"Simplificação",
 "rough_on_off":"Áspero ON/OFF",
 "rough_on":"Áspero ON",
 "rough_off":"Áspero OFF",
 "Multi":"Multi-traço",
 "MultiFill":"Multi-preenchimento",
 side_label_rough:"Áspero", 
 auto_generate:"Geração auto", 
 prompt:"Prompt(β)", 
 prompt_gallery:"Galeria de prompts", 
 loading_image:"Carregando", 
 image_load_error:"Sem imagem"
 },
 th: {
 rought_error:"ข้อผิดพลาดที่ไม่รู้จัก",
 rough_target:"ไม่ได้เลือกเป้าหมายแบบหยาบ",
 rough_target_message:"สามารถใช้เอฟเฟกต์หยาบกับรูปทรง ไอคอน และบอลลูนอิสระได้",
 "Rough":"หยาบ(β)",
 "strokeColor":"สีเส้น",
 "fillStyle":"สไตล์การเติม",
 "fill_style":"สไตล์การเติม",
 "fillWeight":"น้ำหนักการเติม",
 "rough_style":"สไตล์พื้นฐาน",
 "roughness":"ความหยาบ",
 "bowing":"ความโค้ง",
 "strokeWidth":"ความหนาเส้น",
 "rough_hachure":"ตั้งค่าลายเส้น",
 "hachureAngle":"มุมลายเส้น",
 "hachureGap":"ช่องว่างลายเส้น",
 "rough_curve":"เส้นโค้ง",
 "curveStepCount":"จำนวนขั้นโค้ง",
 "curveFitting":"การปรับโค้ง",
 "simplification":"การทำให้ง่าย",
 "rough_on_off":"หยาบ เปิด/ปิด",
 "rough_on":"หยาบ เปิด",
 "rough_off":"หยาบ ปิด",
 "Multi":"หลายเส้น",
 "MultiFill":"หลายการเติม",
 side_label_rough:"หยาบ", 
 auto_generate:"สร้างอัตโนมัติ", 
 prompt:"พรอมต์(β)", 
 prompt_gallery:"แกลเลอรีพรอมต์", 
 loading_image:"กำลังโหลด", 
 image_load_error:"ไม่มีภาพ"
 },
 de: {
 rought_error:"Unbekannter Fehler",
 rough_target:"Kein Rau-Ziel ausgewählt",
 rough_target_message:"Rau-Effekt kann auf Formen, Icons und freie Sprechblasen angewendet werden.",
 "Rough":"Rau(β)",
 "strokeColor":"Strichfarbe",
 "fillStyle":"Füllstil",
 "fill_style":"Füllstil",
 "fillWeight":"Füllgewicht",
 "rough_style":"Grundstil",
 "roughness":"Rauheit",
 "bowing":"Biegung",
 "strokeWidth":"Strichbreite",
 "rough_hachure":"Schraffur-Einstellungen",
 "hachureAngle":"Schraffur-Winkel",
 "hachureGap":"Schraffur-Abstand",
 "rough_curve":"Kurve",
 "curveStepCount":"Kurvenschritte",
 "curveFitting":"Kurvenanpassung",
 "simplification":"Vereinfachung",
 "rough_on_off":"Rau EIN/AUS",
 "rough_on":"Rau EIN",
 "rough_off":"Rau AUS",
 "Multi":"Mehrfach-Strich",
 "MultiFill":"Mehrfach-Füllung",
 side_label_rough:"Rau", 
 auto_generate:"Auto-Generierung", 
 prompt:"Prompt(β)", 
 prompt_gallery:"Prompt-Galerie", 
 loading_image:"Wird geladen", 
 image_load_error:"Kein Bild"
 }
},
"20250301_v2": {
ja: {view_Layer:"レイヤー",view_AI:"AI"},
en: {view_Layer:"Layer",view_AI:"AI"},
ko: {view_Layer:"레이어",view_AI:"AI"},
fr: {view_Layer:"Calque",view_AI:"IA"},
zh: {view_Layer:"图层",view_AI:"AI"},
ru: {view_Layer:"Слой",view_AI:"ИИ"},
es: {view_Layer:"Capa",view_AI:"IA"},
pt: {view_Layer:"Camada",view_AI:"IA"},
th: {view_Layer:"เลเยอร์",view_AI:"เอไอ"},
de: {view_Layer:"Ebene",view_AI:"KI"}
},
"20250301": {
ja: {terms_of_service:"利用規約"},
en: {terms_of_service:"Terms of Service"},
ko: {terms_of_service:"서비스 이용약관"},
fr: {terms_of_service:"Conditions d'utilisation"},
zh: {terms_of_service:"服务条款"},
ru: {terms_of_service:"Условия использования"},
es: {terms_of_service:"Términos de servicio"},
pt: {terms_of_service:"Termos de serviço"},
th: {terms_of_service:"ข้อกำหนดการให้บริการ"},
de: {terms_of_service:"Nutzungsbedingungen"}
},
"base": {
  ja: base_ja,en: base_en,ko: base_ko,fr: base_fr,zh: base_zh,ru: base_ru,es: base_es,pt: base_pt,th: base_th,de: base_de
}
};

function mergeResources(resources) {
const mergedResources = {};

if (resources.base) {
  Object.keys(resources.base).forEach(function(lang) {
    mergedResources[lang] = {
      translation: Object.assign({}, resources.base[lang])
    };
  });
}

Object.keys(resources)
  .filter(function(key) { return key !== 'base'; })
  .sort()
  .forEach(function(dateKey) {
    Object.keys(resources[dateKey]).forEach(function(lang) {
      if (!mergedResources[lang]) {
        mergedResources[lang] = { translation: {} };
      }
      
      Object.assign(
        mergedResources[lang].translation,
        resources[dateKey][lang]
      );
    });
  });

return mergedResources;
}

const mergedResources = mergeResources(resources);
let savedLanguage = localStorage.getItem("language") || "en";

i18next.init(
{
  lng: savedLanguage,
  resources: mergedResources,
},
function (err, t) {
  updateContent();
  setLanguage(savedLanguage);
}
);

function updateContent() {
document.querySelectorAll("[data-i18n]").forEach(function (element) {
  const key = element.getAttribute("data-i18n");
  const translation = i18next.t(key);
  if (translation) {
    if (element.tagName === "OPTION") {
      element.textContent = translation;
    } else {
      element.innerHTML = translation;
    }
  } else {
    uiLogger.warn(`Translation for key "${key}" not found.`);
  }
});
document.querySelectorAll("[data-i18n-label]").forEach(function (element) {
  const key = element.getAttribute("data-i18n-label");
  element.setAttribute("data-label", i18next.t(key));
});
}

function changeLanguage(lng, event) {
if (event) {
  event.preventDefault();
}
i18next.changeLanguage(lng, function (err, t) {
  if (!err) {
    createToast("Save Language", "successfully!");
    localStorage.setItem("language", lng);
    updateContent();
    setLanguage(lng);
    updateLayerPanel();
    savedLanguage = lng;
    if (objectMenu && objectMenu.style.display === "flex") {
      showObjectMenu(lastClickType);
    }
  } else {
    uiLogger.error("Failed to change language:", err);
  }
});
recreateFloatingWindow();
}

function getTranslation(key, defaultText) {
const translatedText = i18next.t(key);
return translatedText !== key ? translatedText : defaultText;
}

function getText(key) {
const translatedText = i18next.t(key);
return translatedText !== key ? translatedText : key;
}