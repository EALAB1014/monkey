import {
    AvailablePlugin,
    PluginMetadataResponse
} from '@/redux/features/api/plugins/types';

export const generatePluginId = (
    name: string,
    pluginType: string,
    version: string
): string => {
    return `${name}-${pluginType}-${version}`;
};

export const parsePluginMetadataResponse = (
    response: PluginMetadataResponse
): AvailablePlugin[] => {
    const plugins: AvailablePlugin[] = [];
    for (const pluginType in response) {
        for (const pluginName in response[pluginType]) {
            const unparsedPlugin =
                response[pluginType][pluginName].slice(-1)[0];
            const availablePlugin: AvailablePlugin = {
                id: generatePluginId(
                    unparsedPlugin.name,
                    unparsedPlugin.plugin_type,
                    unparsedPlugin.version
                ),
                name: unparsedPlugin.name,
                pluginType: unparsedPlugin.plugin_type,
                description: unparsedPlugin.description,
                safe: unparsedPlugin.safe,
                version: unparsedPlugin.version,
                resourcePath: unparsedPlugin.resource_path,
                sha256: unparsedPlugin.sha256
            };
            plugins.push(availablePlugin);
        }
    }
    return plugins;
};
