function generateSteps(){
var steps=[
{element:'#intro_svg-container-vertical',intro:i18next.t('introBodySidePanelVertical'),title:i18next.t('introTitleSidePanelVertical')},
{element:'#intro_svg-container-landscape',intro:i18next.t('introBodySidePanelHorizontal'),title:i18next.t('introTitleSidePanelHorizontal')},
{element:'#intro_page-manager-area',intro:i18next.t('introBodySidePanelPageM'),title:i18next.t('introTitleSidePanelPageM')},
{element:'#intro_custom-panel-manager-area',intro:i18next.t('introBodySidePanelM'),title:i18next.t('introTitleSidePanelM')},
{element:'#intro_speech-bubble-area1',intro:i18next.t('introBodySidePanelSB1'),title:i18next.t('introTitleSidePanelSB1')},
{element:'#intro_speech-bubble-area2',intro:i18next.t('introBodySidePanelSB2'),title:i18next.t('introTitleSidePanelSB2')},
{element:'#intro_text-area',intro:i18next.t('introBodySidePanelText'),title:i18next.t('introTitleSidePanelText')},
{element:'#intro_text-area2',intro:i18next.t('introBodySidePanelText2'),title:i18next.t('introTitleSidePanelText2')},
{element:'#intro_tool-area',intro:i18next.t('introBodySidePanelTool'),title:i18next.t('introTitleSidePanelTool')},
{element:'#intro_manga-tone-area',intro:i18next.t('introBodySidePanelTone'),title:i18next.t('introTitleSidePanelTone')},
{element:'#intro_manga-effect-area',intro:i18next.t('introBodySidePanelEffect'),title:i18next.t('introTitleSidePanelEffect')},
{element:'#intro_controle-area',intro:i18next.t('introBodySidePanelControle'),title:i18next.t('introTitleSidePanelControle')},
{element:'#intro_shape-area',intro:i18next.t('introBodySidePanelShape'),title:i18next.t('introTitleSidePanelShape')},
{element:'#intro_content',intro:i18next.t('intro_content_body'),title:i18next.t('intro_content_title')},
{element:'#intro_sdWebUI',intro:i18next.t('intro_sdWebUI_body'),title:i18next.t('intro_sdWebUI_title')}
];
return steps;
}
function tutorialIntroLegacy(){
var intro=introJs();
intro.setOptions({steps:generateSteps()});
intro.start();
}
